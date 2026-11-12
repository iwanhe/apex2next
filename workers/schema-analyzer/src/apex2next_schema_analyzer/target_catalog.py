"""R3 target catalog: column types of the migrated PostgreSQL schema, for the application generator.

The APEX export does not carry column types for classic report and Cards regions, and a view column type
cannot be derived safely from text. The migrated target schema is the authority, so the types are read from
the PostgreSQL catalog once and stored next to the schema plan (``db/target-catalog.json``).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .app_generator import CATALOG_FORMAT

QUERY = """
select c.relname, a.attname, format_type(a.atttypid, a.atttypmod)
  from pg_attribute a
  join pg_class c on c.oid = a.attrelid
  join pg_namespace n on n.oid = c.relnamespace
 where n.nspname = %s and c.relkind in ('r', 'v', 'm', 'p') and a.attnum > 0 and not a.attisdropped
 order by c.relname, a.attnum
"""


def read_catalog(database_url: str, schema: str) -> dict[str, Any]:
    import psycopg

    relations: dict[str, dict[str, str]] = {}
    with psycopg.connect(database_url) as conn:
        conn.read_only = True
        for relation, column, pg_type in conn.execute(QUERY, (schema,)).fetchall():
            relations.setdefault(relation, {})[column] = pg_type
    return {"format": CATALOG_FORMAT, "schema": schema, "relations": relations}


def main() -> int:
    parser = argparse.ArgumentParser(description="Read the column types of a migrated PostgreSQL schema (R3)")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--schema", default="app")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog = read_catalog(args.database_url, args.schema)
    if not catalog["relations"]:
        raise SystemExit(f"schema {args.schema} has no tables or views; run the migrations first")
    args.output.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(catalog['relations'])} relations -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
