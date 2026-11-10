"""WP9.7 migration rehearsal for app 170134: load, fail-closed rerun, injected failure, retry, backup, restore.

Every step runs against a disposable PostgreSQL database (DATABASE_URL) and is timed. Nothing touches Oracle.

  R1  clean target: drop schema app, apply the reviewed migrations
  R2  load the snapshot (snapshot_migration.migrate: one transaction, commits only if every check passes)
  R3  rerun the load on the loaded target: must fail closed (LOD-001) and leave the data unchanged
  R4  injected failure: a copy of the snapshot whose last loaded table violates a foreign key -> LOD-002,
      the whole load rolls back (every table empty again)
  R5  retry after the failure: the real snapshot loads with every check PASS
  R6  backup: pg_dump -Fc of schemas app and iam (local accounts) (file kept outside Git; size and SHA-256 recorded)
  R7  simulated loss: drop schemas app and iam
  R8  restore: pg_restore, then table/view comparison with the snapshot, identity high-water marks, and an API
      smoke test (health/ready, dev login, report rows) on the restored database

RTO of the rehearsal = R7 start .. R8 end (restore + verification). RPO is the age of the backup used.

Usage (from examples/f170134-target, after `pnpm build`):
  DATABASE_URL=postgresql://... python3 rehearsal/rehearse.py --snapshot snapshot-s4.csv --backup-dir /tmp/wp97 \
      --output ../../docs/migration/wp9.7/f170134/rehearsal.json
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "workers" / "schema-analyzer" / "src"))
sys.path.insert(0, str(ROOT / "e2e"))

from apex2next_schema_analyzer.snapshot_migration import (  # noqa: E402
    compare_state, compare_views_after, migrate, parse_snapshot,
)
from conftest import _free_port, _wait  # noqa: E402

TABLES = ["apx_demo_roles", "apx_demo_user_roles", "apx_demo_departments", "apx_demo_items", "apx_demo_doc_types",
          "apx_demo_doc_seq", "apx_demo_requests", "apx_demo_request_lines", "apx_demo_approvals"]


class Steps:
    def __init__(self):
        self.items: list[dict] = []

    def run(self, sid: str, title: str, fn):
        t0 = time.perf_counter()
        try:
            detail = fn() or {}
            ok = detail.pop("ok", True)
        except Exception as exc:  # noqa: BLE001 - a rehearsal step reports, never hides, its failure
            ok, detail = False, {"error": f"{type(exc).__name__}: {exc}"}
        ms = round((time.perf_counter() - t0) * 1000)
        self.items.append({"id": sid, "title": title, "result": "PASS" if ok else "FAIL", "ms": ms, **detail})
        print(f"{sid} {'PASS' if ok else 'FAIL'} {ms} ms {title}", file=sys.stderr)
        return ok


def counts(db: str) -> dict[str, int]:
    import psycopg
    with psycopg.connect(db) as c:
        return {t: c.execute(f"SELECT count(*) FROM app.{t}").fetchone()[0] for t in TABLES}


def migrate_schema(db: str) -> None:
    import psycopg
    with psycopg.connect(db, autocommit=True) as c:
        c.execute("DROP SCHEMA IF EXISTS app CASCADE")
        c.execute("DROP SCHEMA IF EXISTS iam CASCADE")
    subprocess.run(["node", "apps/api/scripts/migrate.mjs"], cwd=ROOT, env={**os.environ, "ALLOW_DB_RESET": "1"},
                   check=True, stdout=subprocess.DEVNULL)


def load(db: str, snap, plan, name: str) -> dict:
    import psycopg
    with psycopg.connect(db) as conn:
        return migrate(conn, snap, plan, snapshot_name=name)


def compare(db: str, snap) -> dict:
    import psycopg
    with psycopg.connect(db) as conn:
        state = compare_state(conn, snap)
        views = compare_views_after(conn, snap)
    t_diff = sum(len(v["differences"]) for v in state.values())
    v_diff = sum(len(v["differences"]) for v in views["views"].values())
    return {"tables": f"{sum(not v['differences'] for v in state.values())}/{len(state)}",
            "views": f"{sum(not v['differences'] for v in views['views'].values())}/{len(views['views'])}",
            "ok": t_diff == 0 and v_diff == 0}


def identities(db: str) -> dict:
    """Next identity value per table must stay above the data and at/after Oracle's LAST_NUMBER after restore."""
    import psycopg
    out = {}
    with psycopg.connect(db) as c:
        rows = c.execute("""SELECT c.relname, a.attname, pg_get_serial_sequence('app.' || c.relname, a.attname)
                              FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'app'
                              JOIN pg_attribute a ON a.attrelid = c.oid AND a.attidentity <> ''""").fetchall()
        for table, col, seq in rows:
            mx = c.execute(f"SELECT coalesce(max({col}), 0) FROM app.{table}").fetchone()[0]
            last, called = c.execute(f"SELECT last_value, is_called FROM {seq}").fetchone()
            nxt = last + 1 if called else last  # setval(n, false) after the load: the next value is n itself
            out[table] = {"next": nxt, "maxKey": mx}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--backup-dir", type=Path, required=True, help="outside the repository; the dump is not committed")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    db = os.environ["DATABASE_URL"]
    text = args.snapshot.read_text(encoding="utf-8")
    snap = parse_snapshot(text)
    plan = json.loads((ROOT / "db" / "schema-plan.json").read_text(encoding="utf-8"))
    args.backup_dir.mkdir(parents=True, exist_ok=True)
    dump = args.backup_dir / "f170134-target.dump"
    steps = Steps()
    started = datetime.now(timezone.utc)

    steps.run("R1", "Clean target and apply the reviewed migrations", lambda: (migrate_schema(db), {})[1])

    def r2():
        rep = load(db, snap, plan, args.snapshot.name)
        return {"checks": rep["checks"], "committed": rep["committed"], "rows": sum(counts(db).values()), "ok": rep["committed"]}
    steps.run("R2", "Load the snapshot (single transaction, all checks)", r2)

    def r3():
        before = counts(db)
        rep = load(db, snap, plan, args.snapshot.name)
        after = counts(db)
        return {"checks": rep["checks"], "committed": rep["committed"], "unchanged": before == after,
                "ok": not rep["committed"] and rep["checks"].get("LOD-001") == "FAIL" and before == after
                and compare(db, snap)["ok"]}
    steps.run("R3", "Rerun on the loaded target fails closed and changes nothing", r3)

    def r4():
        migrate_schema(db)
        bad = copy.deepcopy(snap)
        line = next(iter(bad.rows["APX_DEMO_REQUEST_LINES"].values()))
        line["item_id"] = 999_999  # no such item: the last FK-ordered tables fail after earlier ones were inserted
        rep = load(db, bad, plan, "injected-fk-failure")
        left = counts(db)
        return {"checks": rep["checks"], "committed": rep["committed"], "problem": rep["problems"][0]["message"][:160],
                "rowsLeft": sum(left.values()), "ok": not rep["committed"] and sum(left.values()) == 0}
    steps.run("R4", "Injected mid-load failure rolls the whole load back", r4)

    account: dict = {}

    def r5():
        rep = load(db, snap, plan, args.snapshot.name)
        # a local account (schema iam) for the API smoke after the restore: proves accounts are in the backup
        out = subprocess.run(["node", "apps/api/scripts/accounts.mjs", "create", "demo_admin", "--by", "REHEARSAL"], cwd=ROOT,
                             env=os.environ, check=True, capture_output=True, text=True).stdout
        account["temp"] = out.split("temporary password: ", 1)[1].split()[0] if "temporary password" in out else None
        return {"checks": rep["checks"], "committed": rep["committed"], "localAccount": "DEMO_ADMIN" if account["temp"] else None,
                "ok": rep["committed"] and compare(db, snap)["ok"] and bool(account["temp"])}
    steps.run("R5", "Retry after the failure loads with every check PASS (+ local account DEMO_ADMIN)", r5)

    def r6():
        subprocess.run(["pg_dump", "-Fc", "--no-owner", "-n", "app", "-n", "iam", "-f", str(dump), db], check=True)
        return {"bytes": dump.stat().st_size, "sha256": hashlib.sha256(dump.read_bytes()).hexdigest(),
                "takenAt": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    steps.run("R6", "Backup (pg_dump custom format, schemas app and iam)", r6)

    rto_start = time.perf_counter()
    import psycopg

    def r7():
        with psycopg.connect(db, autocommit=True) as c:
            c.execute("DROP SCHEMA app CASCADE")
            c.execute("DROP SCHEMA IF EXISTS iam CASCADE")
            gone = c.execute("SELECT count(*) FROM pg_namespace WHERE nspname IN ('app', 'iam')").fetchone()[0] == 0
        return {"ok": gone}
    steps.run("R7", "Simulated loss: schemas app and iam dropped", r7)

    def r8():
        subprocess.run(["pg_restore", "--no-owner", "--exit-on-error", "-d", db, str(dump)], check=True)
        cmp_ = compare(db, snap)
        idn = identities(db)
        idn_ok = all(v["next"] > v["maxKey"] for v in idn.values()) and all(
            (idn.get(t.split('.')[0].lower(), {}).get("next") or 0) >= (i.get("last_number") or 0) for t, i in snap.identities.items())
        smoke = api_smoke(db, account.get("temp") or "")
        return {"comparison": {k: v for k, v in cmp_.items() if k != "ok"}, "identities": idn, "apiSmoke": smoke,
                "ok": cmp_["ok"] and idn_ok and smoke["ok"]}
    steps.run("R8", "Restore and verify (tables, views, identities, API smoke)", r8)
    rto_ms = round((time.perf_counter() - rto_start) * 1000)

    report = {
        "format": "apex2next.wp97-rehearsal.v1",
        "snapshot": {"name": args.snapshot.name, "sha256": snap.sha256, "sourceSysdate": snap.session.get("sysdate")},
        "target": {"database": urlparse(db).path.lstrip("/"), "postgres": server_version(db)},
        "startedAt": started.isoformat(timespec="seconds"),
        "steps": steps.items,
        "rtoMeasuredMs": rto_ms,
        "result": "PASS" if all(s["result"] == "PASS" for s in steps.items) else "FAIL",
        "note": "Rehearsal by the engineer on a disposable database; not witnessed. Backup file kept outside Git.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(f"{report['result']} RTO {rto_ms} ms", file=sys.stderr)
    return 0 if report["result"] == "PASS" else 1


def server_version(db: str) -> str:
    import psycopg
    with psycopg.connect(db) as c:
        return c.execute("SHOW server_version").fetchone()[0]


def api_smoke(db: str, temp_password: str) -> dict:
    """Restored database, AUTH_MODE=local: the account created before the backup signs in with its temporary
    password, must change it, and then reads the reports."""
    port = _free_port()
    env = {**os.environ, "DATABASE_URL": db, "AUTH_MODE": "local", "API_PORT": str(port),
           "SESSION_SECRET": "rehearsal-session-secret-0123456789abcdef"}
    api = subprocess.Popen(["node", "dist/main.js"], cwd=ROOT / "apps/api", env=env, stdout=subprocess.DEVNULL,
                           stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    try:
        _wait(f"{base}/health")
        ready = json.loads(urllib.request.urlopen(f"{base}/health/ready", timeout=10).read())
        def post(path, body, token=None):
            r = urllib.request.Request(base + path, method="POST", data=json.dumps(body).encode(),
                                       headers={"content-type": "application/json",
                                                **({"authorization": f"Bearer {token}"} if token else {})})
            return json.loads(urllib.request.urlopen(r, timeout=30).read())
        first = post("/auth/login", {"username": "demo_admin", "password": temp_password})
        new_password = "Rehearsal" + secrets.token_hex(4) + "9"
        token = post("/auth/password", {"current": temp_password, "next": new_password, "confirm": new_password},
                     first["token"])["token"]

        def get(path):
            r = urllib.request.Request(base + path, headers={"authorization": f"Bearer {token}"})
            return json.loads(urllib.request.urlopen(r, timeout=10).read())
        lines = get("/regions/requestLines?all=1")["rows"]
        summary = get("/regions/requestSummary?all=1")["rows"]
        return {"ready": ready.get("status"), "authMode": "local", "forcedPasswordChange": first.get("mustChangePassword"),
                "requestLines": len(lines), "requestSummary": len(summary),
                "ok": ready.get("status") in ("ok", "ready") and first.get("mustChangePassword") is True
                and len(lines) > 0 and len(summary) > 0}
    finally:
        api.terminate()
        api.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
