from apex2next_extractor.ui_generator import build_ui_spec, build_ui_generator_files


def _document():
    return {
        "irVersion": "1.0.0",
        "application": {"id": "app:demo", "name": "Demo"},
        "objects": [
            {"id": "page:10", "type": "PAGE", "sourceType": "page", "name": "Orders",
             "properties": {}, "source": {"file": "p10.apx", "line": 1}},
            {"id": "item:10", "type": "ITEM", "sourceType": "page_item", "name": "Order Number",
             "parentId": "page:10", "properties": {
                 "label": {"valueType": "STRING", "value": "Order number"},
                 "required": {"valueType": "BOOLEAN", "value": True},
                 "source": {"valueType": "SQL_EXPRESSION", "rawExpression": "select secret from dual"},
             }},
            {"id": "process:10", "type": "PROCESS", "sourceType": "process", "name": "Save order",
             "parentId": "page:10", "properties": {
                 "source": {"valueType": "PL_SQL_EXPRESSION", "rawExpression": "BEGIN NULL; END;"},
             }},
            {"id": "region:10", "type": "REGION", "sourceType": "region", "name": "Orders report",
             "parentId": "page:10", "properties": {}},
            {"id": "item:orphan", "type": "ITEM", "sourceType": "page_item", "name": "Orphan",
             "parentId": "missing:page", "properties": {}},
        ],
        "relationships": [], "references": [], "dependencies": [], "diagnostics": [],
        "metadata": {"sourceHash": "sha256:fixture", "adapterVersion": "0.1.0"},
    }


def test_ui_spec_groups_page_components_and_keeps_manual_work_explicit():
    spec = build_ui_spec(_document())
    assert spec["format"] == "apex2next.generated-ui-spec.v1"
    assert len(spec["pages"]) == 1
    page = spec["pages"][0]
    assert page["route"] == "orders-" + __import__("hashlib").sha256(b"page:10").hexdigest()[:8]
    assert [component["id"] for component in page["components"]] == ["item:10", "process:10", "region:10"]
    item = page["components"][0]
    assert item["presentation"] == {"label": "Order number", "required": True}
    assert page["components"][1]["reviewStatus"] == "MANUAL_REVIEW"
    assert spec["unassignedComponentIds"] == ["item:orphan"]
    assert spec["safety"]["sourceExpressionsIncluded"] is False


def test_ui_generator_emits_web_api_and_review_artifacts_without_source_expressions():
    files = build_ui_generator_files(_document())
    assert "apps/web/lib/apex2next-generated-spec.ts" in files
    assert "apps/api/src/generated/apex2next-generated-spec.ts" in files
    assert "apps/web/components/GeneratedPageInventory.tsx" in files
    assert "migration-report/ui-generation.json" in files
    route = next(path for path in files if path.startswith("apps/web/app/pages/"))
    assert "GeneratedPageInventory" in files[route]
    assert "select secret from dual" not in files["apps/web/lib/apex2next-generated-spec.ts"]
    assert "BEGIN NULL; END;" not in files["apps/api/src/generated/apex2next-generated-spec.ts"]


def test_ui_generator_is_deterministic():
    assert build_ui_generator_files(_document()) == build_ui_generator_files(_document())
