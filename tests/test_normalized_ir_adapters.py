from pathlib import Path

from apex2next_extractor.ir_schema import validate_ir_document
from apex2next_extractor.normalized_ir import (
    adapt_apex_export,
    adapt_apexlang_directory,
    object_fingerprint,
    stable_identity,
    resolve_references,
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
    assert page["properties"]["p_source"]["valueType"] == "UNKNOWN"
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


def test_reference_resolver_reports_dangling_candidate() -> None:
    source_document = adapt_apexlang_directory(FIXTURE)
    resolved = resolve_references(source_document)

    assert resolved["references"][0]["resolutionStatus"] == "DANGLING"
    assert any(item["code"] == "REF001" for item in resolved["diagnostics"])
    assert resolved["dependencies"] == []


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
