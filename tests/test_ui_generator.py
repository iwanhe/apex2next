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
                 "displayAs": {"valueType": "STRING", "value": "NATIVE_TEXT_FIELD"},
                 "placeholder": {"valueType": "STRING", "value": "Enter order number"},
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


def test_ui_spec_keeps_navigation_lovs_and_authorization_as_review_metadata():
    doc = _document()
    doc["objects"].extend([
        {"id": "lov:status", "type": "LOV", "sourceType": "lov", "name": "STATUS_LOV",
         "properties": {"source": {"valueType": "SQL_EXPRESSION", "rawExpression": "select secret from dual"}}},
        {"id": "auth:admin", "type": "AUTHORIZATION", "sourceType": "authorization",
         "name": "ADMIN_ONLY", "properties": {}},
        {"id": "list:main", "type": "LIST", "sourceType": "list", "name": "Main Navigation",
         "properties": {}},
    ])
    spec = build_ui_spec(doc)
    assert spec["navigation"][0]["name"] == "Main Navigation"
    assert spec["lovs"][0]["reviewStatus"] == "MANUAL_REVIEW"
    assert spec["authorizationSchemes"][0]["name"] == "ADMIN_ONLY"
    assert "select secret from dual" not in str(spec)


def test_ui_generator_emits_report_and_form_definitions_as_manual_stubs():
    files = build_ui_generator_files(_document())
    assert "apps/api/src/generated/report-definitions.ts" in files
    assert "apps/api/src/generated/form-definitions.ts" in files
    assert "migration-report/report-generation.json" in files
    assert "migration-report/form-generation.json" in files
    assert "MANUAL_REVIEW" in files["apps/api/src/generated/form-definitions.ts"]
    assert "queryGenerated" in files["apps/api/src/generated/report-definitions.ts"]


def test_form_and_report_contracts_capture_safe_metadata_but_never_claim_runtime_binding():
    files = build_ui_generator_files(_document())
    form = files["apps/api/src/generated/form-definitions.ts"]
    report = files["apps/api/src/generated/report-definitions.ts"]
    assert '"fieldType": "TEXT"' in form
    assert '"label": "Order number"' in form
    assert '"required": true' in form
    assert '"placeholder": "Enter order number"' in form
    assert '"bindingStatus": "NOT_BOUND"' in form
    assert '"queryGenerated": false' in report
    assert '"pagination": {' in report
    assert '"bindingStatus": "NOT_BOUND"' in report
    assert '"bindingsGenerated": false' in files["migration-report/form-generation.json"]
    assert '"bindingsGenerated": false' in files["migration-report/report-generation.json"]



def test_static_literal_lovs_generate_safe_web_adapter_and_keep_dynamic_lovs_manual():
    doc = _document()
    doc["objects"][1]["properties"]["namedLov"] = {
        "valueType": "STRING", "value": "ORDER_STATUS"
    }
    doc["objects"].extend([
        {"id": "lov:static", "type": "LOV", "sourceType": "lov", "name": "ORDER_STATUS",
         "properties": {"staticValues": {"valueType": "ARRAY", "value": [
             {"display": "Open", "return": "O"},
             {"display": "Closed", "return": "C"},
         ]}}},
        {"id": "lov:dynamic", "type": "LOV", "sourceType": "lov", "name": "CUSTOMER_LOV",
         "properties": {"source": {"valueType": "SQL_EXPRESSION",
                                   "rawExpression": "select secret from customer"}}},
    ])
    spec = build_ui_spec(doc)
    static = next(item for item in spec["lovs"] if item["id"] == "lov:static")
    dynamic = next(item for item in spec["lovs"] if item["id"] == "lov:dynamic")
    assert static["adapterStatus"] == "STATIC_LITERAL"
    assert static["staticValues"] == [
        {"display": "Open", "return": "O"}, {"display": "Closed", "return": "C"}
    ]
    assert dynamic["adapterStatus"] == "MANUAL_REVIEW"
    assert "select secret" not in str(spec)
    files = build_ui_generator_files(doc)
    generated = files["apps/web/lib/generated-lovs.ts"]
    assert '"ORDER_STATUS"' in generated
    assert '"display": "Open"' in generated
    assert '"CUSTOMER_LOV"' not in generated
    assert '"dynamicAdaptersGenerated": false' in files["migration-report/lov-generation.json"]
    assert '"namedLov": "ORDER_STATUS"' in files["apps/web/lib/apex2next-generated-spec.ts"]
