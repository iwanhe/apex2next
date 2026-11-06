from apex2next_extractor.ir_schema import load_ir_schema, validate_ir_document


def minimal_ir() -> dict:
    return {
        "irVersion": "1.0.0",
        "application": {"id": "app:demo", "sourceFormat": "APEXLANG"},
        "objects": [],
        "relationships": [],
        "references": [],
        "dependencies": [],
        "diagnostics": [],
        "metadata": {"sourceHash": "sha256:demo", "adapterVersion": "0.1.0"},
    }


def test_schema_is_valid_json_schema_2020_12() -> None:
    schema = load_ir_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["irVersion"]["const"] == "1.0.0"


def test_accepts_minimal_ir_document() -> None:
    assert validate_ir_document(minimal_ir()) == []


def test_preserves_unknown_object_types_and_properties() -> None:
    document = minimal_ir()
    document["objects"] = [
        {
            "id": "obj:future:1",
            "type": "UNKNOWN",
            "sourceType": "FutureComponent",
            "properties": {
                "futureSetting": {
                    "valueType": "UNKNOWN",
                    "rawExpression": "futureFeature(enabled => true)",
                    "preserved": True,
                }
            },
            "source": {"file": "future.apx", "line": 1, "column": 1},
            "extensions": {"originalDeclaration": "FutureComponent"},
        }
    ]
    assert validate_ir_document(document) == []


def test_rejects_missing_required_top_level_fields() -> None:
    diagnostics = validate_ir_document({"irVersion": "1.0.0"})
    assert diagnostics
    assert all(item["code"] == "IR001" for item in diagnostics)
    assert all(item["severity"] == "ERROR" for item in diagnostics)


def test_rejects_unsupported_ir_version() -> None:
    document = minimal_ir()
    document["irVersion"] = "2.0.0"
    diagnostics = validate_ir_document(document)
    assert any("1.0.0" in item["message"] for item in diagnostics)
