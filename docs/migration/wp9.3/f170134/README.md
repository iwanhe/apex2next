# WP9.3 generated artifacts — Demo Permintaan Barang (170134)

These files are **generated**. Do not edit them by hand. Change conversion rules or decisions, then regenerate.
`tests/test_wp93_f170134_artifacts.py` pins them to the source hash
`sha256:7c71e9c56b76d5fe893d2f357e692b9e7c458adc37791784379842ec1712d66d` and to the current rule
registry. CI fails if a rule changes without regenerating these files.

The source `install.sql` and the APEX export are not committed (WP9.1/9.2 chain-of-custody policy).

```bash
# from the repository root, with the reviewed inputs unpacked outside the repo
export PYTHONPATH=workers/schema-analyzer/src:workers/extraction-worker/src
D=docs/migration/wp9.3/f170134
python -m apex2next_schema_analyzer.schema_plan /path/to/install.sql --source-name install.sql \
  --apex-export /path/to/f170134/application --overrides $D/dictionary-overrides.json \
  --output $D/schema-plan.json --sql-output $D/0001_wp93_schema.sql \
  --post-load-output $D/post-load-identity-alignment.sql
python -m apex2next_schema_analyzer.schema_report $D/schema-plan.json --output $D/schema-conversion-report.md \
  --title "WP9.3 — Schema Conversion Report: Demo Permintaan Barang (170134)"

# WP9.3b dictionary reconciliation (CSV from sql/dictionary_inventory_apex_workshop.sql, not committed)
# dictionary-overrides.json was built from USER_VIEWS text (report_1.csv):
#   python -m apex2next_schema_analyzer.source_overrides report_1.csv --view APX_DEMO_DASH_KPI_V --dictionary report.csv --reason "..." --output $D/dictionary-overrides.json
python -m apex2next_schema_analyzer.dictionary_reconciliation $D/schema-plan.json /path/to/install.sql /path/to/report.csv \
  --view-texts /path/to/report_1.csv --overrides $D/dictionary-overrides.json \
  --output $D/dictionary-reconciliation.json --markdown-output $D/dictionary-reconciliation.md \
  --title "WP9.3b — Oracle Dictionary Reconciliation: Demo Permintaan Barang (170134)"

# prove byte-identical regeneration and run PostgreSQL integration tests (disposable DB only)
APEX2NEXT_F170134_INSTALL_SQL=/path/to/install.sql APEX2NEXT_F170134_DICTIONARY_CSV=/path/to/report.csv APEX2NEXT_F170134_VIEW_TEXTS_CSV=/path/to/report_1.csv APEX2NEXT_F170134_EXPORT_DIR=/path/to/f170134/application \
APEX2NEXT_TEST_DATABASE_URL=postgresql://user@host/disposable_db python -m pytest tests/test_wp93*.py
```
