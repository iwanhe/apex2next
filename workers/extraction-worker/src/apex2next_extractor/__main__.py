"""Command line entry point: python -m apex2next_extractor <export.sql>."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .apex_export import extract_export


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract static metadata from an Oracle APEX export")
    parser.add_argument("export_file", type=Path)
    parser.add_argument("--output", type=Path, help="Write JSON output to this path")
    args = parser.parse_args()

    result = extract_export(args.export_file.read_text(encoding="utf-8", errors="replace"))
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 1 if any(item["severity"] == "ERROR" for item in result["diagnostics"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
