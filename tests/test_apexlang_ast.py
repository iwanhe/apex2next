from apex2next_extractor.apexlang_ast import parse_apexlang_ast, tokenize_apexlang


def test_tokenizer_preserves_source_offsets_and_multiline_spans() -> None:
    source = "page 10 (\n  name: 'Orders'\n)\n"
    tokens, diagnostics = tokenize_apexlang(source)
    page = next(token for token in tokens if token.value == "page")
    literal = next(token for token in tokens if token.value == "'Orders'")
    assert diagnostics == []
    assert (page.span.start_line, page.span.start_column) == (1, 1)
    assert (literal.span.start_line, literal.span.start_column) == (2, 9)
    assert source[literal.span.start_offset:literal.span.end_offset] == "'Orders'"


def test_ast_builds_nested_declaration_tree_without_counting_string_content() -> None:
    source = """page 10 (
    name: 'fake region 99 ('
    region grid (
        name: 'Orders'
        process save (
            source: 'begin null; end;'
        )
    )
)
"""
    ast = parse_apexlang_ast(source)
    assert ast.diagnostics == []
    assert len(ast.declarations) == 1
    page = ast.declarations[0]
    assert (page.kind, page.name) == ("page", "10")
    assert [(child.kind, child.name) for child in page.children] == [("region", "grid")]
    assert [(child.kind, child.name) for child in page.children[0].children] == [("process", "save")]
    assert "fake region 99" in page.raw_body


def test_ast_preserves_fenced_blocks_and_ignores_comments() -> None:
    source = """page 10 (
    // region fake (
    sql: ~~~sql
    select 'page 99 (' from dual
    ~~~
)
"""
    ast = parse_apexlang_ast(source)
    assert len(ast.declarations) == 1
    assert [node.kind for node in ast.declarations[0].children] == []
    assert any(token.kind == "RAW_BLOCK" for token in ast.tokens)
    assert ast.diagnostics == []


def test_ast_reports_unterminated_declarations_and_strings() -> None:
    ast = parse_apexlang_ast("page 10 (\n name: 'unterminated\n")
    assert {item["code"] for item in ast.diagnostics} >= {"AST003", "AST004"}



def test_ast_balances_parentheses_inside_multiline_property_expressions() -> None:
    source = """page 10 (
    source: coalesce(
        lookup_value(foo(1, 2)),
        'fallback'
    )
    region grid (
        name: 'Orders'
    )
)
"""
    ast = parse_apexlang_ast(source)
    assert ast.diagnostics == []
    page = ast.declarations[0]
    assert page.raw_body.rstrip().endswith(")")
    assert [(node.kind, node.name) for node in page.children] == [("region", "grid")]
    assert "lookup_value(foo(1, 2))" in page.raw_body



def test_ast_parses_typed_scalar_object_and_array_properties_with_spans() -> None:
    source = """page 10 (
    title: 'Orders'
    enabled: true
    retries: 3
    config: {
        mode: 'strict'
        timeout: 2.5
    }
    columns: [
        'ORDER_ID',
        'ORDER_DATE',
        'TOTAL'
    ]
)
"""
    ast = parse_apexlang_ast(source)
    page = ast.declarations[0]
    props = {prop.name: prop for prop in page.properties}
    assert props["title"].value_type == "STRING"
    assert props["title"].value == "Orders"
    assert props["enabled"].value_type == "BOOLEAN"
    assert props["enabled"].value is True
    assert props["retries"].value_type == "NUMBER"
    assert props["retries"].value == 3
    assert props["config"].value_type == "OBJECT"
    assert [(p.name, p.value) for p in props["config"].children] == [
        ("mode", "strict"), ("timeout", 2.5)
    ]
    assert props["columns"].value_type == "ARRAY"
    assert props["columns"].value == ["ORDER_ID", "ORDER_DATE", "TOTAL"]
    assert props["config"].span.start_line == 5
    assert props["config"].span.end_line == 8
    assert ast.diagnostics == []


def test_ast_property_parser_preserves_duplicate_keys_and_unknown_expressions() -> None:
    source = """page 10 (
    source: coalesce(
        lookup_value(foo(1, 2)),
        'fallback'
    )
    source: :P10_SOURCE
)
"""
    ast = parse_apexlang_ast(source)
    page = ast.declarations[0]
    assert len([prop for prop in page.properties if prop.name == "source"]) == 2
    assert page.properties[0].value_type == "EXPRESSION"
    assert "lookup_value(foo(1, 2))" in page.properties[0].raw_value
    assert page.properties[1].value_type == "EXPRESSION"
    assert any(item["code"] == "AST102" for item in ast.diagnostics)


def test_nested_declaration_properties_do_not_leak_into_parent_property_scope() -> None:
    source = """page 10 (
    title: 'Page'
    region grid (
        title: 'Region'
        process save (
            source: 'begin null; end;'
        )
    )
)
"""
    ast = parse_apexlang_ast(source)
    page = ast.declarations[0]
    region = page.children[0]
    assert [(prop.name, prop.value) for prop in page.properties] == [("title", "Page")]
    assert [(prop.name, prop.value) for prop in region.properties] == [("title", "Region")]
    assert [(prop.name, prop.value) for prop in region.children[0].properties] == [
        ("source", "begin null; end;")
    ]


def test_ast_supports_nested_objects_arrays_and_inline_mixed_values() -> None:
    source = """page 10 (
    settings: { mode: 'strict', retries: 3, nested: { enabled: true } }
    columns: [
        'ORDER_ID',
        { name: 'TOTAL', options: ['sum', 'avg'] },
        ['A', 'B']
    ]
)
"""
    ast = parse_apexlang_ast(source)
    props = {prop.name: prop for prop in ast.declarations[0].properties}
    settings = props["settings"]
    assert settings.value_type == "OBJECT"
    assert [(p.name, p.value) for p in settings.children] == [
        ("mode", "strict"), ("retries", 3), ("nested", {"enabled": True})
    ]
    columns = props["columns"]
    assert columns.value_type == "ARRAY"
    assert [item.value_type for item in columns.items] == ["STRING", "OBJECT", "ARRAY"]
    object_item = columns.items[1]
    assert [(p.name, p.value) for p in object_item.children] == [
        ("name", "TOTAL"), ("options", ["sum", "avg"])
    ]
    assert columns.items[0].span.start_offset < columns.items[1].span.start_offset
    assert ast.diagnostics == []


def test_ast_property_parser_preserves_expression_and_nested_duplicate_diagnostics() -> None:
    source = """page 10 (
    config: {
        name: 'first',
        name: 'second',
        expression: build_value(
            nested_call(1, 2),
            'x,y'
        )
    }
)
"""
    ast = parse_apexlang_ast(source)
    config = ast.declarations[0].properties[0]
    assert [p.name for p in config.children] == ["name", "name", "expression"]
    assert "nested_call(1, 2)" in config.children[2].raw_value
    assert sum(d["code"] == "AST102" for d in ast.diagnostics) == 1


def test_ast_reports_resource_limits_without_recursing_or_executing() -> None:
    oversized = parse_apexlang_ast("page 1 ()", max_source_chars=4)
    assert oversized.diagnostics[0]["code"] == "AST900"
    too_many_tokens = parse_apexlang_ast("page 1 ()", max_tokens=2)
    assert too_many_tokens.diagnostics[0]["code"] == "AST901"
    too_deep = parse_apexlang_ast("page 1 (" + "(" * 5 + ")" * 5 + ")", max_nesting_depth=3)
    assert too_deep.diagnostics[-1]["code"] == "AST903"


def test_ast_parser_handles_deterministic_malformed_input_corpus() -> None:
    # Small deterministic fuzz-style corpus: malformed delimiters, strings, and comments.
    samples = [
        "page 1 ( config: { a: [1, 2 } )",
        "page 2 ( source: call(1, 2\n region x ( name: 'x' ) )",
        "page 3 ( title: 'unterminated )",
        "page 4 ( /* comment never closes",
        "page 5 ( values: [[[[[]]]]] )",
        "page 6 ( data: { a: { b: { c: true } } } )",
    ]
    for source in samples:
        ast = parse_apexlang_ast(source)
        assert isinstance(ast.declarations, list)
        assert isinstance(ast.diagnostics, list)
