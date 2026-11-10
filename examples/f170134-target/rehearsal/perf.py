"""WP9.7 light performance test for app 170134 on synthetic volume (indicative, not a capacity test).

1. Disposable database (DATABASE_URL, must be a throw-away database): migrate, load the snapshot, then add synthetic
   volume with plain SQL (request_no 'SYN-…', created_by 'SYNTHETIC'): --requests requests with 3 lines each and one
   approval step for every submitted/approved request. No real data is generated or copied.
2. Start the built API (AUTH_MODE=dev) and drive the read paths the pages use, plus request creation, with a thread
   pool: --users concurrent users, --iterations requests per scenario. Latency is measured client side.
3. Report p50/p95/max/errors per scenario and the volume, as JSON.

Usage (from examples/f170134-target, after `pnpm build`):
  DATABASE_URL=postgresql://.../f170134_perf python3 rehearsal/perf.py --snapshot snapshot-s4.csv --output perf.json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "workers" / "schema-analyzer" / "src"))
sys.path.insert(0, str(ROOT / "e2e"))

from apex2next_schema_analyzer.snapshot_migration import migrate, parse_snapshot  # noqa: E402
from conftest import DEV_PASSWORD, _free_port, _wait  # noqa: E402

SYNTHETIC_SQL = """
INSERT INTO app.apx_demo_requests (request_no, department_id, request_date, need_date, purpose, status,
                                   created_by, created_on, updated_by, updated_on)
SELECT 'SYN-' || lpad(g::text, 6, '0'), 1 + g % 3, DATE '2026-01-01' + (g % 300), DATE '2026-01-15' + (g % 300),
       'Synthetic request ' || g,
       (ARRAY['DRAFT','DRAFT','SUBMITTED','APPROVED','REJECTED','FULFILLED'])[1 + g % 6],
       'SYNTHETIC', TIMESTAMP '2026-01-01 08:00' + make_interval(mins => g), 'SYNTHETIC',
       TIMESTAMP '2026-01-01 08:00' + make_interval(mins => g)
  FROM generate_series(1, %(n)s) g;
INSERT INTO app.apx_demo_request_lines (request_id, item_id, qty, unit_price, created_by, created_on, updated_by, updated_on)
SELECT r.request_id, 1 + (r.request_id + k) % 5, 1 + (r.request_id * k) % 20, (ARRAY[55000,30000,12500000,150000,450000])[1 + (r.request_id + k) % 5],
       'SYNTHETIC', r.created_on, 'SYNTHETIC', r.created_on
  FROM app.apx_demo_requests r CROSS JOIN generate_series(1, 3) k
 WHERE r.request_no LIKE 'SYN-%%';
INSERT INTO app.apx_demo_approvals (doc_type, doc_id, doc_no, approval_level, approver_role, amount, requested_by,
                                    requested_on, status, acted_by, acted_on, note)
SELECT 'REQ', r.request_id, r.request_no, 1, 'MANAGER',
       (SELECT sum(l.line_amount) FROM app.apx_demo_request_lines l WHERE l.request_id = r.request_id),
       'SYNTHETIC', r.created_on,
       CASE r.status WHEN 'SUBMITTED' THEN 'PENDING' WHEN 'REJECTED' THEN 'REJECTED' ELSE 'APPROVED' END,
       CASE WHEN r.status = 'SUBMITTED' THEN NULL ELSE 'SYNTHETIC' END,
       CASE WHEN r.status = 'SUBMITTED' THEN NULL ELSE r.created_on END, NULL
  FROM app.apx_demo_requests r
 WHERE r.request_no LIKE 'SYN-%%' AND r.status IN ('SUBMITTED', 'APPROVED', 'REJECTED', 'FULFILLED');
ANALYZE;
"""

SCENARIOS = [
    # (id, user, method, path, body) - the read paths of pages 100, 190, 300, 310, 400 and a write (page 301 create)
    ("S1 dashboard (page 100)", "demo_admin", "GET", "/pages/100", None),
    ("S2 requests + facets (page 300)", "demo_admin", "GET", "/regions/requests", None),
    ("S3 requests facet DRAFT + search (page 300)", "demo_admin", "GET", "/regions/requests?facet=P300_STATUS%3ADRAFT&q=request%201", None),
    ("S4 lines IR default (page 310)", "demo_admin", "GET", "/regions/requestLines", None),
    ("S5 lines IR search + sort (page 310)", "demo_admin", "GET", "/regions/requestLines?q=laptop&sort=line_amount&dir=desc", None),
    ("S6 lines IR last page (page 310)", "demo_admin", "GET", "/regions/requestLines?page=1200", None),
    ("S7 summary IR sort total (page 400)", "demo_admin", "GET", "/regions/requestSummary?sort=total_amount&dir=desc", None),
    ("S8 approval inbox (page 190)", "demo_mgr", "GET", "/regions/approvalInbox", None),
    ("S9 create request (page 301)", "demo_req", "POST", "/forms/request",
     {"values": {"department_id": "2", "request_date": datetime.now(timezone.utc).date().isoformat(),
                 "need_date": "2099-12-31", "purpose": "Perf test"}}),  # API dates are ISO; the web formats DD-MON-YYYY
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--requests", type=int, default=20000)
    ap.add_argument("--users", type=int, default=10)
    ap.add_argument("--iterations", type=int, default=200)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    db = os.environ["DATABASE_URL"]
    import psycopg

    with psycopg.connect(db, autocommit=True) as c:
        c.execute("DROP SCHEMA IF EXISTS app CASCADE")
    subprocess.run(["node", "apps/api/scripts/migrate.mjs"], cwd=ROOT, env={**os.environ, "ALLOW_DB_RESET": "1"},
                   check=True, stdout=subprocess.DEVNULL)
    plan = json.loads((ROOT / "db" / "schema-plan.json").read_text(encoding="utf-8"))
    with psycopg.connect(db) as conn:
        rep = migrate(conn, parse_snapshot(args.snapshot.read_text(encoding="utf-8")), plan, snapshot_name=args.snapshot.name)
    if not rep["committed"]:
        print(json.dumps(rep["checks"]), file=sys.stderr)
        return 2
    t0 = time.perf_counter()
    with psycopg.connect(db, autocommit=True) as c:
        c.execute(SYNTHETIC_SQL.replace("%(n)s", str(int(args.requests))).replace("%%", "%"))
        volume = {t: c.execute(f"SELECT count(*) FROM app.{t}").fetchone()[0]
                  for t in ("apx_demo_requests", "apx_demo_request_lines", "apx_demo_approvals")}
    gen_ms = round((time.perf_counter() - t0) * 1000)

    port = _free_port()
    env = {**os.environ, "AUTH_MODE": "dev", "DEV_LOGIN_PASSWORD": DEV_PASSWORD, "API_PORT": str(port),
           "SESSION_SECRET": "perf-session-secret-0123456789abcdef0123"}
    api = subprocess.Popen(["node", "dist/main.js"], cwd=ROOT / "apps/api", env=env, stdout=subprocess.DEVNULL,
                           stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    try:
        _wait(f"{base}/health")
        tokens = {u: login(base, u) for u in {s[1] for s in SCENARIOS}}
        results = []
        for sid, user, method, path, body in SCENARIOS:
            for _ in range(5):  # warm-up
                call(base, tokens[user], method, path, body)
            with ThreadPoolExecutor(max_workers=args.users) as pool:
                t_start = time.perf_counter()
                samples = list(pool.map(lambda _: call(base, tokens[user], method, path, body), range(args.iterations)))
                wall = time.perf_counter() - t_start
            ms = sorted(s[0] for s in samples)
            errors = [s[1] for s in samples if s[1] >= 400]
            results.append({"scenario": sid, "method": method, "path": path, "n": len(ms),
                            "p50": round(statistics.median(ms), 1), "p95": round(ms[int(0.95 * (len(ms) - 1))], 1),
                            "max": round(ms[-1], 1), "throughputPerSec": round(len(ms) / wall, 1),
                            "errors": len(errors), "statuses": sorted(set(s[1] for s in samples))})
            print(f"{sid}: p50 {results[-1]['p50']} ms p95 {results[-1]['p95']} ms errors {len(errors)}", file=sys.stderr)
    finally:
        api.terminate()
        api.wait(timeout=10)

    report = {
        "format": "apex2next.wp97-performance.v1",
        "runAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment": {"postgres": pg_version(db), "node": subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip(),
                        "cpus": os.cpu_count(), "host": "disposable cloud sandbox (shared CPU); API and database on the same host",
                        "auth": "AUTH_MODE=dev"},
        "load": {"concurrentUsers": args.users, "iterationsPerScenario": args.iterations, "warmup": 5},
        "volume": {**volume, "synthetic": True, "generationMs": gen_ms, "baseSnapshot": args.snapshot.name},
        "results": results,
        "note": "Indicative only: shared sandbox hardware, no network between tiers, no APEX baseline at this volume.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


def login(base: str, user: str) -> str:
    req = urllib.request.Request(f"{base}/auth/login", method="POST", headers={"content-type": "application/json"},
                                 data=json.dumps({"username": user, "password": DEV_PASSWORD}).encode())
    return json.loads(urllib.request.urlopen(req, timeout=10).read())["token"]


def call(base: str, token: str, method: str, path: str, body) -> tuple[float, int]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, method=method, data=data,
                                 headers={"authorization": f"Bearer {token}", "content-type": "application/json"})
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        status = e.code
    return (time.perf_counter() - t) * 1000, status


def pg_version(db: str) -> str:
    import psycopg
    with psycopg.connect(db) as c:
        return c.execute("SHOW server_version").fetchone()[0]


if __name__ == "__main__":
    raise SystemExit(main())
