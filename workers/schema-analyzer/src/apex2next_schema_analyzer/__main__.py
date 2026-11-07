"""CLI: python -m apex2next_schema_analyzer <ddl.sql> [--output inventory.json]."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .inventory import analyze_ddl


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory object headers in Oracle DDL text")
    parser.add_argument("ddl_file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = analyze_ddl(args.ddl_file.read_text(encoding="utf-8", errors="replace"))
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 1 if any(item["severity"] == "ERROR" for item in result["diagnostics"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
