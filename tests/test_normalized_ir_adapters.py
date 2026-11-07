from pathlib import Path

import apex2next_extractor.normalized_ir as normalized_ir_module
from apex2next_extractor.apexlang_ast import ApexLangAst, ApexLangDeclaration, SourceSpan
from apex2next_extractor.ir_schema import validate_ir_document
from apex2next_extractor.normalized_ir import (
    adapt_apex_export,
    adapt_apexlang_directory,
    object_fingerprint,
    stable_identity,
    resolve_references,
    classify_expression,
)


FIXTURE = Path("tests/fixtures/apexlang-26.2")


def test_apexlang_adapter_emits_schema_valid_ir_and_provenance() -> None:
    document = adapt_apexlang_directory(FIXTURE)

    assert validate_ir_document(document) == []
    assert document["application"]["sourceFormat"] == "APEXLANG"
    assert document["application"]["sourceVersion"]["metadataVersion"] == "26.2.0+3479"
    assert document["application"]["sourceVersion"]["runtimeVersion"] is None
    assert len(document["objects"]) == 5

    app_object = next(obj for obj in document["objects"] if obj["type"] == "APPLICATION")
    page = next(obj for obj in document["objects"] if obj["type"] == "PAGE" and obj["name"] == "10")
    region = next(obj for obj in document["objects"] if obj["type"] == "REGION")

    assert app_object["id"] == document["application"]["id"]
    assert app_object["parentId"] is None
    assert page["source"]["file"] == "pages/p10.apx"
    assert page["source"]["line"] == 1
    assert page["source"]["artifactHash"].startswith("sha256:")
    assert region["parentId"] == page["id"]
    assert any(ref["referenceValue"] == "requester" for ref in document["references"])
    assert any(item["code"] == "SRC002" for item in document["diagnostics"])


def test_apex_export_adapter_preserves_raw_arguments_and_is_schema_valid() -> None:
    source = """begin
      wwv_flow_imp.create_flow(
        p_id => 100,
        p_name => 'Demo App'
      );
      wwv_flow_imp_page.create_page(
        p_id => 10,
        p_name => 'Orders',
        p_source => q'[select * from orders where status = 'OPEN']'
      );
      wwv_flow_imp_page.create_page_item(
        p_id => 101,
        p_name => 'P10_ORDER_ID'
      );
    end;
    """
    document = adapt_apex_export(source, "f100.sql")

    assert validate_ir_document(document) == []
    assert document["application"]["sourceFormat"] == "APEX_SQL_EXPORT"
    assert document["application"]["id"] == next(
        obj["id"] for obj in document["objects"] if obj["type"] == "APPLICATION"
    )
    page = next(obj for obj in document["objects"] if obj["type"] == "PAGE")
    assert page["source"]["apiRoutine"] == "create_page"
    assert page["source"]["line"] == 6
    assert page["properties"]["p_source"]["valueType"] == "SQL_EXPRESSION"
    assert page["properties"]["p_source"]["expressionLanguage"] == "SQL"
    assert page["properties"]["p_source"]["classificationConfidence"] == "HIGH"
    assert "select * from orders" in page["properties"]["p_source"]["rawExpression"]
    assert page["extensions"]["rawArguments"]["p_source"].startswith("q'[")


def test_unknown_export_routine_is_preserved_as_unknown_object() -> None:
    document = adapt_apex_export(
        "begin wwv_flow_imp_page.create_future_component(p_id => 9, p_config => future(x)); end;",
        "future.sql",
    )

    assert validate_ir_document(document) == []
    assert document["objects"][0]["type"] == "UNKNOWN"
    assert document["objects"][0]["extensions"]["rawArguments"]["p_config"] == "future(x)"
    assert any(item["code"] == "IR002" for item in document["diagnostics"])


def test_stable_identity_survives_content_changes_but_fingerprint_does_not() -> None:
    identity_before = stable_identity("APEXLANG", "PAGE", "10", parent_id="app")
    identity_after = stable_identity("APEXLANG", "PAGE", "10", parent_id="app")
    before = object_fingerprint("PAGE", "page", "Orders", {"title": {"valueType": "STRING", "value": "Orders"}})
    after = object_fingerprint("PAGE", "page", "Orders", {"title": {"valueType": "STRING", "value": "Sales"}})

    assert identity_before == identity_after
    assert before != after


def test_cross_format_adapters_share_the_same_ir_contract_shape() -> None:
    apexlang = adapt_apexlang_directory(FIXTURE)
    export = adapt_apex_export(
        "begin wwv_flow_imp_page.create_page(p_id => 10, p_name => 'Orders'); end;",
        "f100.sql",
    )

    for document in (apexlang, export):
        assert set(document) >= {
            "irVersion", "application", "objects", "relationships",
            "references", "dependencies", "diagnostics", "metadata",
        }
        assert validate_ir_document(document) == []



def test_native_identity_is_scoped_to_parent_for_repeated_component_names() -> None:
    first = stable_identity("APEXLANG", "REGION", "grid", parent_id="page:10")
    second = stable_identity("APEXLANG", "REGION", "grid", parent_id="page:11")

    assert first != second


def test_apexlang_adapter_does_not_collect_references_from_comments_or_literals(tmp_path: Path) -> None:
    source_dir = tmp_path / "apexlang"
    source_dir.mkdir()
    (source_dir / "application.apx").write_text("app DEMO (\n name: 'Demo'\n)\n", encoding="utf-8")
    (source_dir / "page.apx").write_text(
        "page 10 (\n name: 'Orders @literal'\n // @commented\n "
        "security { scheme: @real_reference }\n)\n",
        encoding="utf-8",
    )

    document = adapt_apexlang_directory(source_dir)

    assert [ref["referenceValue"] for ref in document["references"]] == ["real_reference"]



def test_unknown_apexlang_declaration_is_retained_with_diagnostic(tmp_path: Path) -> None:
    source_dir = tmp_path / "unknown-apexlang"
    source_dir.mkdir()
    (source_dir / "future.apx").write_text(
        "futureComponent Widget (\n config: future_expression(x)\n)\n",
        encoding="utf-8",
    )

    document = adapt_apexlang_directory(source_dir)

    assert validate_ir_document(document) == []
    assert len(document["objects"]) == 1
    assert document["objects"][0]["type"] == "UNKNOWN"
    assert document["objects"][0]["sourceType"] == "futureComponent"
    assert "future_expression(x)" in document["objects"][0]["extensions"]["rawDeclarationBody"]
    assert any(item["code"] == "IR002" for item in document["diagnostics"])



def test_reference_resolver_resolves_one_exact_in_scope_candidate(tmp_path: Path) -> None:
    source_dir = tmp_path / "resolved-apexlang"
    source_dir.mkdir()
    (source_dir / "application.apx").write_text(
        "app DEMO (\n name: 'Demo'\n)\nauthorization requester (\n name: 'Requester'\n)\n"
        "page 10 (\n security { scheme: @requester }\n)\n",
        encoding="utf-8",
    )

    source_document = adapt_apexlang_directory(source_dir)
    resolved = resolve_references(source_document)

    assert source_document["references"][0]["resolutionStatus"] == "PENDING"
    assert resolved["references"][0]["resolutionStatus"] == "RESOLVED"
    assert resolved["references"][0]["targetObjectId"] == next(
        obj["id"] for obj in resolved["objects"] if obj["type"] == "AUTHORIZATION"
    )
    assert len(resolved["dependencies"]) == 1
    assert resolved["dependencies"][0]["origin"] == "EXPLICIT"
    assert resolved["metadata"]["resolverVersion"] == "0.1.0"
    assert validate_ir_document(resolved) == []
    assert resolve_references(resolved) == resolved


def test_reference_resolver_reports_dangling_candidate() -> None:
    source_document = adapt_apexlang_directory(FIXTURE)
    resolved = resolve_references(source_document)

    assert resolved["references"][0]["resolutionStatus"] == "DANGLING"
    assert any(item["code"] == "REF001" for item in resolved["diagnostics"])
    assert resolved["dependencies"] == []
    assert validate_ir_document(resolved) == []


def test_reference_resolver_reports_ambiguous_candidates(tmp_path: Path) -> None:
    source_dir = tmp_path / "ambiguous-apexlang"
    source_dir.mkdir()
    (source_dir / "application.apx").write_text(
        "app DEMO (\n name: 'Demo'\n)\nauthorization requester (\n)\n"
        "authentication requester (\n)\npage 10 (\n security { scheme: @requester }\n)\n",
        encoding="utf-8",
    )

    resolved = resolve_references(adapt_apexlang_directory(source_dir))

    assert resolved["references"][0]["resolutionStatus"] == "AMBIGUOUS"
    assert len(resolved["references"][0]["candidateObjectIds"]) == 2
    assert any(item["code"] == "REF002" for item in resolved["diagnostics"])
    assert validate_ir_document(resolved) == []



def test_apexlang_containment_stack_resets_between_source_files(tmp_path: Path) -> None:
    source_dir = tmp_path / "multi-file-apexlang"
    (source_dir / "pages").mkdir(parents=True)
    (source_dir / "application.apx").write_text("app DEMO (\n)\n", encoding="utf-8")
    (source_dir / "pages" / "p10.apx").write_text(
        "page 10 (\n    region grid (\n    )\n)\n", encoding="utf-8"
    )
    (source_dir / "pages" / "p11.apx").write_text(
        "    page 11 (\n        name: 'Second'\n    )\n", encoding="utf-8"
    )

    document = adapt_apexlang_directory(source_dir)
    app_id = document["application"]["id"]
    second_page = next(obj for obj in document["objects"] if obj["type"] == "PAGE" and obj["name"] == "11")

    assert second_page["parentId"] == app_id



def test_reference_resolver_reports_canonical_identity_collisions(tmp_path: Path) -> None:
    source_dir = tmp_path / "collision-apexlang"
    source_dir.mkdir()
    (source_dir / "application.apx").write_text(
        "app DEMO (\n)\nauthorization requester (\n)\n"
        "authorization requester (\n)\npage 10 (\n security { scheme: @requester }\n)\n",
        encoding="utf-8",
    )

    resolved = resolve_references(adapt_apexlang_directory(source_dir))

    assert any(item["code"] == "IR004" for item in resolved["diagnostics"])
    assert resolved["references"][0]["resolutionStatus"] == "AMBIGUOUS"
    assert validate_ir_document(resolved) == []



def test_apexlang_properties_are_typed_and_keep_property_level_provenance(tmp_path: Path) -> None:
    source_dir = tmp_path / "typed-properties"
    source_dir.mkdir()
    (source_dir / "application.apx").write_text(
        "app DEMO (\n    name: 'Demo App'\n)\n",
        encoding="utf-8",
    )
    (source_dir / "page.apx").write_text(
        "page 10 (\n"
        "    title: 'Orders'\n"
        "    enabled: true\n"
        "    pageSize: 25\n"
        "    ratio: 1.25\n"
        "    emptyValue: null\n"
        "    source: select_orders(:P10_ID)\n"
        "    nested {\n"
        "        hidden: 'not-a-direct-property'\n"
        "    }\n"
        ")\n",
        encoding="utf-8",
    )

    document = adapt_apexlang_directory(source_dir)
    page = next(obj for obj in document["objects"] if obj["type"] == "PAGE")

    assert validate_ir_document(document) == []
    assert page["properties"]["title"]["valueType"] == "STRING"
    assert page["properties"]["title"]["value"] == "Orders"
    assert page["properties"]["enabled"]["valueType"] == "BOOLEAN"
    assert page["properties"]["enabled"]["value"] is True
    assert page["properties"]["pageSize"]["valueType"] == "NUMBER"
    assert page["properties"]["pageSize"]["value"] == 25
    assert page["properties"]["ratio"]["valueType"] == "NUMBER"
    assert page["properties"]["ratio"]["value"] == 1.25
    assert page["properties"]["emptyValue"]["valueType"] == "NULL"
    assert page["properties"]["emptyValue"]["value"] is None
    assert page["properties"]["source"]["valueType"] == "UNKNOWN"
    assert page["properties"]["source"]["expressionLanguage"] == "UNKNOWN"
    assert page["properties"]["source"]["rawExpression"] == "select_orders(:P10_ID)"
    assert page["properties"]["source"]["sourceLocator"]["file"] == "page.apx"
    assert page["properties"]["source"]["sourceLocator"]["line"] == 7
    assert page["properties"]["source"]["sourceLocator"]["column"] == 5
    assert page["properties"]["nested"]["valueType"] == "OBJECT"
    assert page["properties"]["nested"]["value"]["hidden"]["value"] == "not-a-direct-property"



def test_apexlang_nested_property_blocks_are_normalized_recursively(tmp_path: Path) -> None:
    source_dir = tmp_path / "nested-properties"
    source_dir.mkdir()
    (source_dir / "application.apx").write_text(
        "app DEMO (\n"
        "    name: 'Demo'\n"
        "    navigation {\n"
        "        homeUrl: {\n"
        "            page: 10\n"
        "            clearCache: '10,RP'\n"
        "        }\n"
        "    }\n"
        ")\n",
        encoding="utf-8",
    )

    document = adapt_apexlang_directory(source_dir)
    app = next(obj for obj in document["objects"] if obj["type"] == "APPLICATION")
    navigation = app["properties"]["navigation"]
    home_url = navigation["value"]["homeUrl"]

    assert validate_ir_document(document) == []
    assert navigation["valueType"] == "OBJECT"
    assert home_url["valueType"] == "OBJECT"
    assert home_url["value"]["page"]["valueType"] == "NUMBER"
    assert home_url["value"]["page"]["value"] == 10
    assert home_url["value"]["clearCache"]["value"] == "10,RP"
    assert navigation["sourceLocator"]["file"] == "application.apx"
    assert navigation["sourceLocator"]["line"] == 3
    assert home_url["sourceLocator"]["line"] == 4
    assert home_url["value"]["page"]["sourceLocator"]["line"] == 5
    assert "navigation {" in app["extensions"]["rawDeclarationBody"]


def test_apexlang_nested_property_expressions_are_preserved(tmp_path: Path) -> None:
    source_dir = tmp_path / "nested-expressions"
    source_dir.mkdir()
    (source_dir / "application.apx").write_text(
        "app DEMO (\n"
        "    settings {\n"
        "        source: select_orders(:P10_ID)\n"
        "        label: 'Text with } brace'\n"
        "    }\n"
        ")\n",
        encoding="utf-8",
    )

    document = adapt_apexlang_directory(source_dir)
    app = next(obj for obj in document["objects"] if obj["type"] == "APPLICATION")
    settings = app["properties"]["settings"]

    assert validate_ir_document(document) == []
    assert settings["value"]["source"]["valueType"] == "UNKNOWN"
    assert settings["value"]["source"]["rawExpression"] == "select_orders(:P10_ID)"
    assert settings["value"]["label"]["value"] == "Text with } brace"



def test_apexlang_multiline_expressions_keep_full_source_and_end_locator(tmp_path: Path) -> None:
    source_dir = tmp_path / "multiline-expression"
    source_dir.mkdir()
    (source_dir / "application.apx").write_text(
        "app DEMO (\n"
        "    name: 'Demo'\n"
        ")\n",
        encoding="utf-8",
    )
    (source_dir / "page.apx").write_text(
        "page 10 (\n"
        "    name: 'Orders'\n"
        "    region grid (\n"
        "        name: 'Orders Grid'\n"
        "    )\n"
        "    source: SELECT order_id,\n"
        "             order_date\n"
        "      FROM orders\n"
        "     WHERE status = 'OPEN'\n"
        "    title: 'Order List'\n"
        ")\n",
        encoding="utf-8",
    )

    document = adapt_apexlang_directory(source_dir)
    page = next(obj for obj in document["objects"] if obj["type"] == "PAGE")

    assert validate_ir_document(document) == []
    assert page["properties"]["source"]["valueType"] == "SQL_EXPRESSION"
    assert page["properties"]["source"]["expressionLanguage"] == "SQL"
    assert page["properties"]["source"]["classificationConfidence"] == "HIGH"
    assert page["properties"]["source"]["rawExpression"] == (
        "SELECT order_id,\norder_date\nFROM orders\nWHERE status = 'OPEN'"
    )
    locator = page["properties"]["source"]["sourceLocator"]
    assert locator["line"] == 6
    assert locator["endLine"] == 9
    assert locator["endColumn"] == 27
    assert "region" not in page["properties"]


def test_apexlang_colon_prefixed_nested_objects_stay_structured(tmp_path: Path) -> None:
    source_dir = tmp_path / "colon-nested"
    source_dir.mkdir()
    (source_dir / "application.apx").write_text(
        "app DEMO (\n"
        "    navigation: {\n"
        "        homeUrl: {\n"
        "            page: 10\n"
        "        }\n"
        "    }\n"
        ")\n",
        encoding="utf-8",
    )

    document = adapt_apexlang_directory(source_dir)
    app = next(obj for obj in document["objects"] if obj["type"] == "APPLICATION")
    navigation = app["properties"]["navigation"]

    assert validate_ir_document(document) == []
    assert navigation["valueType"] == "OBJECT"
    assert navigation["value"]["homeUrl"]["value"]["page"]["value"] == 10



def test_expression_classifier_uses_conservative_syntax_evidence() -> None:
    cases = {
        "SELECT * FROM orders": "SQL",
        "q'[SELECT * FROM orders]'": "SQL",
        "WITH q AS (SELECT 1 FROM dual) SELECT * FROM q": "SQL",
        "BEGIN\n  NULL;\nEND;": "PL_SQL",
        "DECLARE\n  v_count NUMBER;\nBEGIN\n  NULL;\nEND;": "PL_SQL",
        "const total = items.length;": "JAVASCRIPT",
        "async function loadData() { return []; }": "JAVASCRIPT",
        "<div class='notice'>Hello</div>": "HTML",
        "@media screen { .card { display: block; } }": "CSS",
        "&P10_STATUS.": "APEX",
        "return status": "UNKNOWN",
        "status = 'OPEN'": "UNKNOWN",
    }

    for expression, expected in cases.items():
        result = classify_expression(expression)
        assert result["language"] == expected
        assert result["confidence"] == ("HIGH" if expected != "UNKNOWN" else "NONE")


def test_sql_expression_mapping_is_consistent_across_apexlang_and_sql_export(tmp_path: Path) -> None:
    source_dir = tmp_path / "cross-format"
    source_dir.mkdir()
    (source_dir / "application.apx").write_text(
        "app DEMO (\n    name: 'Demo'\n)\n", encoding="utf-8"
    )
    (source_dir / "page.apx").write_text(
        "page 10 (\n    source: SELECT order_id FROM orders\n)\n",
        encoding="utf-8",
    )
    apexlang = adapt_apexlang_directory(source_dir)
    export = adapt_apex_export(
        "begin wwv_flow_imp_page.create_page(p_id => 10, "
        "p_source => q'[SELECT order_id FROM orders]'); end;",
        "f100.sql",
    )

    lang_prop = next(obj for obj in apexlang["objects"] if obj["type"] == "PAGE")["properties"]["source"]
    export_prop = next(obj for obj in export["objects"] if obj["type"] == "PAGE")["properties"]["p_source"]
    assert lang_prop["sourcePropertyName"] == "source"
    assert lang_prop["canonicalPropertyName"] == "source"
    assert export_prop["sourcePropertyName"] == "p_source"
    assert export_prop["canonicalPropertyName"] == "source"

    for prop in (lang_prop, export_prop):
        assert prop["valueType"] == "SQL_EXPRESSION"
        assert prop["expressionLanguage"] == "SQL"
        assert prop["classificationConfidence"] == "HIGH"
        assert prop["classificationRule"] == "EXPR_SQL_STATEMENT_V1"
        assert "SELECT" in prop["rawExpression"].upper()



def test_cross_format_mapping_preserves_source_property_keys_and_unknowns() -> None:
    apexlang = adapt_apexlang_directory(FIXTURE)
    export = adapt_apex_export(
        "begin wwv_flow_imp_page.create_page(p_id => 10, "
        "p_source => custom_expression('keep exact text')); end;",
        "f100.sql",
    )
    export_page = next(obj for obj in export["objects"] if obj["type"] == "PAGE")
    prop = export_page["properties"]["p_source"]

    assert "p_source" in export_page["properties"]
    assert prop["sourcePropertyName"] == "p_source"
    assert prop["canonicalPropertyName"] == "source"
    assert prop["valueType"] == "UNKNOWN"
    assert prop["expressionLanguage"] == "UNKNOWN"
    assert prop["rawExpression"] == "custom_expression('keep exact text')"
    assert validate_ir_document(apexlang) == []
    assert validate_ir_document(export) == []


def test_expression_classification_metadata_is_explicit_for_non_executable_markup() -> None:
    cases = {
        "<section>hello</section>": ("HTML", "UNKNOWN"),
        "@media screen { .card { display: block; } }": ("CSS", "UNKNOWN"),
        "&P10_STATUS.": ("APEX", "UNKNOWN"),
        "return status": ("UNKNOWN", "UNKNOWN"),
    }
    for source, (language, value_type) in cases.items():
        result = classify_expression(source)
        assert result["language"] == language
        assert result["confidence"] in {"HIGH", "NONE"}
        assert value_type == "UNKNOWN"


def test_apexlang_ast_properties_integrate_recursive_arrays_and_source_spans(tmp_path: Path) -> None:
    source_dir = tmp_path / "ast-ir-integration"
    source_dir.mkdir()
    (source_dir / "application.apx").write_text(
        "app DEMO (\n    name: 'AST Integration'\n)\n", encoding="utf-8"
    )
    (source_dir / "page.apx").write_text(
        "page 10 (\n"
        "    items: ['A', { name: 'B', options: [1, 2] }, [true, false]]\n"
        "    source: SELECT order_id FROM orders\n"
        ")\n",
        encoding="utf-8",
    )

    document = adapt_apexlang_directory(source_dir)
    page = next(obj for obj in document["objects"] if obj["type"] == "PAGE")
    items = page["properties"]["items"]

    assert validate_ir_document(document) == []
    assert items["valueType"] == "ARRAY"
    assert document["metadata"]["apexlangAstIntegration"] == "TYPED_PROPERTIES_WITH_LEGACY_FALLBACK"
    assert document["metadata"]["apexlangAstParserVersion"] == "0.2.0"
    assert document["metadata"]["apexlangAstPropertyAdaptedCount"] >= 1
    assert [item["valueType"] for item in items["value"]] == ["STRING", "OBJECT", "ARRAY"]
    nested_object = items["value"][1]
    assert nested_object["value"]["name"]["value"] == "B"
    assert nested_object["value"]["options"]["valueType"] == "ARRAY"
    assert [item["value"] for item in nested_object["value"]["options"]["value"]] == [1, 2]
    assert items["sourceLocator"]["file"] == "page.apx"
    assert items["sourceLocator"]["line"] == 2
    assert items["sourceLocator"]["column"] == 5
    assert items["extensions"]["rawSourceValue"].startswith("[")
    assert page["properties"]["source"]["valueType"] == "SQL_EXPRESSION"
    assert page["properties"]["source"]["rawExpression"] == "SELECT order_id FROM orders"
    assert page["properties"]["source"]["sourceLocator"]["line"] == 3


def test_apexlang_ast_adapter_falls_back_when_property_parity_is_not_proven(tmp_path: Path) -> None:
    source_dir = tmp_path / "ast-parity-fallback"
    source_dir.mkdir()
    (source_dir / "application.apx").write_text("app DEMO (\n)\n", encoding="utf-8")
    (source_dir / "page.apx").write_text(
        "page 10 (\n"
        "    navigation {\n"
        "        homeUrl: { page: 10 }\n"
        "    }\n"
        ")\n",
        encoding="utf-8",
    )

    document = adapt_apexlang_directory(source_dir)
    page = next(obj for obj in document["objects"] if obj["type"] == "PAGE")

    assert validate_ir_document(document) == []
    assert page["properties"]["navigation"]["valueType"] == "OBJECT"
    assert page["properties"]["navigation"]["value"]["homeUrl"]["valueType"] == "UNKNOWN"
    assert "page: 10" in page["properties"]["navigation"]["value"]["homeUrl"]["rawExpression"]
    parity = [item for item in document["diagnostics"] if item["code"] == "IRAST001"]
    assert len(parity) == 1
    assert parity[0]["details"]["astPropertyNames"] == ["homeUrl"]
    assert parity[0]["details"]["inventoryPropertyNames"] == ["navigation"]


def test_apexlang_ast_integrated_ir_is_deterministic_for_fixed_source(tmp_path: Path) -> None:
    source_dir = tmp_path / "deterministic-ast-ir"
    source_dir.mkdir()
    (source_dir / "application.apx").write_text(
        "app DEMO (\n    name: 'Deterministic'\n)\n", encoding="utf-8"
    )
    (source_dir / "page.apx").write_text(
        "page 10 (\n    values: [1, 2, 3]\n)\n", encoding="utf-8"
    )

    first = adapt_apexlang_directory(source_dir)
    second = adapt_apexlang_directory(source_dir)

    assert first == second
    assert validate_ir_document(first) == []



def test_apexlang_adapter_reports_inventory_declarations_without_ast_match(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "inventory-without-ast"
    source_dir.mkdir()
    (source_dir / "page.apx").write_text(
        "page 10 (\n    title: 'Legacy'\n)\n", encoding="utf-8"
    )

    monkeypatch.setattr(
        normalized_ir_module,
        "parse_apexlang_ast",
        lambda _source: ApexLangAst([], [], []),
    )
    document = adapt_apexlang_directory(source_dir)

    assert validate_ir_document(document) == []
    assert len([item for item in document["diagnostics"] if item["code"] == "IRAST002"]) == 1
    page = next(obj for obj in document["objects"] if obj["type"] == "PAGE")
    assert page["properties"]["title"]["value"] == "Legacy"


def test_apexlang_adapter_reports_ast_only_declarations_without_synthesizing_objects(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "ast-only-declaration"
    source_dir.mkdir()
    (source_dir / "future.apx").write_text("# source without inventory declaration\n", encoding="utf-8")
    span = SourceSpan(0, 10, 1, 1, 1, 11)
    ast_node = ApexLangDeclaration(
        kind="futureComponent",
        name="Widget",
        span=span,
        body_span=SourceSpan(10, 10, 1, 11, 1, 11),
        raw_body="",
    )
    monkeypatch.setattr(
        normalized_ir_module,
        "parse_apexlang_ast",
        lambda _source: ApexLangAst([ast_node], [], []),
    )

    document = adapt_apexlang_directory(source_dir)

    assert validate_ir_document(document) == []
    assert document["objects"] == []
    diagnostic = next(item for item in document["diagnostics"] if item["code"] == "IRAST003")
    assert diagnostic["details"] == {"sourceType": "futureComponent", "name": "Widget"}



def test_apexlang_duplicate_direct_properties_are_all_preserved_outside_unique_key_map(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "duplicate-direct-properties"
    source_dir.mkdir()
    (source_dir / "application.apx").write_text(
        "app DEMO (\n    name: 'Duplicate test'\n)\n",
        encoding="utf-8",
    )
    (source_dir / "page.apx").write_text(
        "page 10 (\n"
        "    title: 'First title'\n"
        "    title: 'Second title'\n"
        "    settings: {\n"
        "        label: 'First nested'\n"
        "        label: 'Second nested'\n"
        "    }\n"
        ")\n",
        encoding="utf-8",
    )

    document = adapt_apexlang_directory(source_dir)
    page = next(obj for obj in document["objects"] if obj["type"] == "PAGE")

    assert validate_ir_document(document) == []
    assert page["properties"]["title"]["value"] == "Second title"
    preserved = page["extensions"]["duplicateProperties"]
    assert [item["occurrence"] for item in preserved] == [1, 2]
    assert [item["property"]["value"] for item in preserved] == [
        "First title",
        "Second title",
    ]
    diagnostic = next(
        item for item in document["diagnostics"] if item["code"] == "IRAST004"
    )
    assert diagnostic["details"]["duplicatePropertyNames"] == ["title"]
    nested = page["properties"]["settings"]
    assert nested["value"]["label"]["value"] == "Second nested"
    assert nested["extensions"]["duplicatePropertyNames"] == ["label"]
    assert [
        item["property"]["value"] for item in nested["extensions"]["duplicateProperties"]
    ] == ["First nested", "Second nested"]
