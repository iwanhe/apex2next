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
