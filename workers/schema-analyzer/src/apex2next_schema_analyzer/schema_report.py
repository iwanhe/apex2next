"""Render a WP9.3 schema plan as a deterministic Markdown review report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _esc(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(_esc(c) for c in row) + " |" for row in rows]
    return out


def render_report(plan: dict[str, Any], *, title: str) -> str:
    s = plan["summary"]
    lines = [
        f"# {title}",
        "",
        "> Generated from the schema plan by `apex2next_schema_analyzer.schema_report`. Do not edit by hand;",
        "> regenerate after changing rules or decisions.",
        "",
        f"- **Source:** `{plan['source']['name']}` — {plan['source']['bytes']:,} bytes, `{plan['source']['sha256']}`",
        f"- **Converter:** schema-plan {plan['converterVersion']}, rule registry `sha256:{plan['ruleRegistrySha256']}`",
        f"- **Target schema:** `{plan['targetSchema']}`",
        f"- **Statements accounted:** {s['statements']}",
        f"- **Tables emitted:** {s['tables']['emitted']}/{s['tables']['source']} · "
        f"**Views emitted:** {s['views']['emitted']}/{s['views']['source']} · "
        f"**Indexes emitted:** {s['indexes']['emitted']}/{s['indexes']['source']}",
        f"- **Dependency validation passed:** {'yes' if s['validationPassed'] else 'NO — see failures below'}",
        "",
        "## 1. Disposition summary",
        "",
    ]
    rows = []
    for kind, counts in s["objectsByType"].items():
        rows.append([kind] + [counts.get(d, 0) for d in ("AUTOMATIC", "ASSISTED", "MANUAL", "UNSUPPORTED")])
    lines += _table(["Object type", "AUTOMATIC", "ASSISTED", "MANUAL", "UNSUPPORTED"], rows)
    lines += ["", "## 2. Dependency validation", ""]
    lines += _table(["Check", "Status", "Title", "Failures / notes"],
                    [[c["id"], c["status"], c["title"],
                      "; ".join(c["failures"]) if c["failures"] else ("; ".join(c["notes"][:12]) or "—")]
                     for c in plan["checks"]])
    lines += ["", "## 3. Tables and columns", ""]
    rows = []
    for t in plan["tables"]:
        obj = next(o for o in plan["objects"] if o["type"] == "TABLE" and o["name"] == t["name"])
        rows.append([t["targetName"], obj["disposition"], "yes" if t["emit"] else "no", len(t["columns"]),
                     ", ".join(obj["findingCodes"]), "; ".join(t.get("omitted", [])) or "—"])
    lines += _table(["Table", "Disposition", "Emitted", "Columns", "Findings", "Omitted elements"], rows)
    lines += ["", "### Type mapping", ""]
    rows = []
    for t in plan["tables"]:
        for c in t["columns"]:
            special = []
            if c.get("identity"):
                special.append(c["identity"]["target"])
            if c.get("generated"):
                special.append(f"GENERATED ALWAYS AS ({c['generated'].get('target', c['generated']['source'])}) STORED")
            if c.get("default"):
                special.append(f"DEFAULT {c['default'].get('target') or '(omitted: ' + c['default']['source'] + ')'}")
            rows.append([f"{t['targetName']}.{c['targetName']}", c["sourceType"] or "(virtual)", c["targetType"],
                         "NULL" if c["nullable"] else "NOT NULL", "; ".join(special) or "—",
                         ", ".join(sorted({f["code"] for f in c["findings"]})) or "—"])
    lines += _table(["Column", "Oracle", "PostgreSQL", "Null", "Identity / generated / default", "Findings"], rows)
    lines += ["", "## 4. Constraints, identity and indexes", ""]
    rows = []
    for o in plan["objects"]:
        if o["type"] in {"PRIMARY KEY", "UNIQUE", "CHECK", "FOREIGN KEY", "IDENTITY", "GENERATED COLUMN", "INDEX"}:
            rows.append([o["type"], o["name"].lower(), o.get("table", "").lower(), o["disposition"],
                         "yes" if o["emitted"] else ("covered by constraint" if o.get("covered") else "no"),
                         ", ".join(o["findingCodes"]) or "—"])
    lines += _table(["Type", "Name", "Table", "Disposition", "Emitted", "Findings"], rows)
    lines += ["", "## 5. Views (dependency order)", ""]
    rows = []
    for v in plan["views"]:
        obj = next(o for o in plan["objects"] if o["type"] == "VIEW" and o["name"] == v["name"])
        rows.append([v["dependencyOrder"], v["name"].lower(), obj["disposition"], "yes" if v["emit"] else "no",
                     ", ".join(d.lower() for d in v["dependencies"]), ", ".join(obj["findingCodes"]), v["design"]])
    lines += _table(["#", "View", "Disposition", "Emitted", "Depends on", "Findings", "Target design"], rows)
    lines += ["", "## 6. Trigger behavior inventory (WP9.4 input)", ""]
    for trg in plan["triggers"]:
        events = " OR ".join(e["event"] + (" OF " + ", ".join(e["columns"]) if e.get("columns") else "") for e in trg["events"])
        lines += [f"### {trg['name'].lower()} — {trg['timing']} {events} ON {str(trg['table']).lower()}"
                  f"{' FOR EACH ROW' if trg['forEachRow'] else ''}", ""]
        lines.append(f"- Behaviors: {', '.join(trg['behaviors']) or '—'}")
        lines.append(f"- Calls: {', '.join(c.lower() for c in trg['calls']) or '—'}; tables read: "
                     f"{', '.join(t.lower() for t in trg['tablesRead']) or '—'}")
        if trg["errors"]:
            lines.append("- Errors raised: " + "; ".join(f"{e['code']} {e['message'] or ''}".strip() for e in trg["errors"]))
        flags = [n for n, v in (("ORA-04091 handler", trg["mutatingTableHandler"]), ("package bypass state", trg["usesBypassState"])) if v]
        if flags:
            lines.append("- Oracle-specific: " + ", ".join(flags))
        lines.append("- Columns written:")
        for col, writes in trg["columnsWritten"].items():
            for w in writes:
                lines.append(f"  - `{col.lower()}` ← `{w['expression']}` ({w['classification']}; {w['branch']})")
        lines.append("- Target design:")
        lines += [f"  - {d}" for d in trg["targetDesign"]]
        lines.append("")
    lines += ["## 7. PL/SQL units (WP9.4 input)", ""]
    lines += _table(["Unit", "Kind", "Members (spec)", "Tables", "Units", "Lexical findings"],
                    [[u["name"].lower(), u["kind"], ", ".join(m.lower() for m in u["members"]) or "—",
                      ", ".join(t.lower() for t in u["tablesReferenced"]) or "—",
                      ", ".join(x.lower() for x in u["unitsReferenced"]) or "—",
                      ", ".join(f"{k}×{v}" for k, v in u["lexicalDiagnostics"].items()) or "—"]
                     for u in plan["plsqlUnits"]])
    lines += ["", "## 8. Data statements (WP9.6 input)", ""]
    lines += _table(["Line", "Statement", "Target", "Disposition"],
                    [[d["line"], d["verb"], (d["target"] or "(PL/SQL block)").lower(), "MANUAL (DAT001)"]
                     for d in plan["dataStatements"]])
    if plan.get("apexReferences") is not None:
        lines += ["", "## 9. APEX consumer references", ""]
        lines += _table(["Kind", "Consumer", "Object", "Columns / member", "Resolved as"],
                        [[r["kind"], r["source"], r["object"].lower(),
                          (r.get("member") or ", ".join(c.lower() for c in r.get("columns", []))) or "—",
                          r.get("resolvedAs", "UNRESOLVED")] for r in plan["apexReferences"]])
    lines += ["", "## 10. Load plan (WP9.6 input)", ""]
    lines += _table(["Table", "Insert columns", "Excluded generated", "Identity"],
                    [[t, ", ".join(v["columns"]), ", ".join(v["excludedGenerated"]) or "—",
                      "; ".join(f"{k}: {m}" for k, m in v["identity"].items()) or "—"]
                     for t, v in plan["loadPlan"].items()])
    lines += ["", "## Limitations", ""] + [f"- {x}" for x in plan["limitations"]] + [""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a schema plan JSON as Markdown")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--title", default="WP9.3 Schema Conversion Report")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    args.output.write_text(render_report(plan, title=args.title), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
