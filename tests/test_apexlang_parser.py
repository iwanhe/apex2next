from pathlib import Path

from apex2next_extractor.apexlang import extract_apexlang, parse_apexlang_text


def test_parses_declarations_and_nested_parentheses_without_counting_text() -> None:
    source = """page 10 (
    name: 'Orders'
    region grid (
        name: Orders
    )
    process save (
        source: 'page fake ('
    )
)
"""
    result = parse_apexlang_text(source, "pages/p10.apx")
    assert [item["object_type"] for item in result["declarations"]] == [
        "PAGE", "REGION", "PROCESS"
    ]
    assert result["declarations"][0]["properties"]["name"] == "Orders"
    assert result["declarations"][1]["name"] == "grid"


def test_extracts_demo_directory_inventory() -> None:
    root = Path("tests/fixtures/apexlang-26.2")
    result = extract_apexlang(root)
    assert result["apexlang_mmd_version"] == "26.2.0+3479"
    assert result["summary"]["page_count"] == 2
    assert result["summary"]["object_counts"]["APPLICATION"] == 1
    assert "requester" in result["references"]


def test_ignores_references_inside_comments_and_string_literals() -> None:
    result = parse_apexlang_text("""page 10 (
    name: '@not-a-reference'
    // @commented-out
    security { scheme: @requester }
)
""")
    assert result["references"] == ["requester"]


def test_ignores_declaration_like_text_inside_fenced_sql() -> None:
    source = """page 10 (
    source {
        sqlQuery:
            ~~~sql
            select 'page 99 (' as text from dual
            ~~~
    }
)
"""
    result = parse_apexlang_text(source)
    assert [item["object_type"] for item in result["declarations"]] == ["PAGE"]
    assert result["diagnostics"] == []


def test_reports_unterminated_declaration() -> None:
    result = parse_apexlang_text("page 10 (\n name: Home\n", "broken.apx")
    assert result["diagnostics"][0]["code"] == "APEXLANG001"
