from apex2next_extractor.query_migration import build_query_migration_plan


def _document():
    return {
        "application": {"id": "app:query", "name": "Query fixture"},
        "objects": [
            {"id": "region:1", "type": "REGION", "name": "Orders report", "properties": {
                "source": {"valueType": "SQL_EXPRESSION", "expressionLanguage": "SQL",
                           "rawExpression": "select nvl(order_total, 0) from dual"},
            }},
            {"id": "region:2", "type": "REGION", "name": "Unknown report", "properties": {
                "source": {"valueType": "SQL_EXPRESSION", "expressionLanguage": "SQL",
                           "rawExpression": "select mystery_function(x) from orders"},
            }},
            {"id": "process:1", "type": "PROCESS", "name": "Save", "properties": {
                "source": {"valueType": "PL_SQL_EXPRESSION", "expressionLanguage": "PL_SQL",
                           "rawExpression": "BEGIN NULL; END;"},
            }},
        ],
    }


def test_sql_query_plan_uses_registered_rewrites_and_records_findings():
    plan = build_query_migration_plan(_document())
    assert plan["queryCount"] == 2
    first, second = plan["queries"]
    assert "COALESCE" in first["targetSql"]
    assert "DUAL" not in first["targetSql"].upper()
    assert first["disposition"] == "ASSISTED"
    assert second["disposition"] == "MANUAL"
    assert second["unresolvedReferences"] == ["ORDERS"]
    assert plan["safety"]["executed"] is False
    assert all(query["executionEnabled"] is False for query in plan["queries"])