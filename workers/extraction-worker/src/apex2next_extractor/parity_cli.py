"""CLI for offline APEX-to-target functional parity comparison."""
from __future__ import annotations

import argparse
import json
import sys

from .parity import compare_parity_files


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare paired APEX and target test evidence.")
    parser.add_argument("manifest", help="Path to a functional-parity-input.v1 JSON manifest")
    parser.add_argument("--output", required=True, help="Path for the deterministic JSON report")
    args = parser.parse_args()
    try:
        report = compare_parity_files(args.manifest, args.output)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"parity error: {error}", file=sys.stderr)
        return 2
    print(json.dumps({
        "status": report["status"],
        "summary": report["summary"],
        "output": args.output,
    }, sort_keys=True))
    return 1 if report["status"] == "FAIL" else 0 if report["status"] == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
