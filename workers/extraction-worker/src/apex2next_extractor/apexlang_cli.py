"""Command line entry point for the APEXLang static inventory parser."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .apexlang import extract_apexlang


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory an APEXLang source directory safely")
    parser.add_argument("source_dir", type=Path, help="Directory containing .apx files")
    parser.add_argument("--output", type=Path, help="Write JSON output to this path")
    args = parser.parse_args()
    rendered = json.dumps(extract_apexlang(args.source_dir), indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
