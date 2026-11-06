from apex2next_extractor import extract_export


def test_extracts_page_and_item_calls_with_nested_arguments() -> None:
    source = """
    begin
      wwv_flow_imp_page.create_page(
        p_id => 10,
        p_name => 'Order, Header',
        p_alias => 'ORDER-HEADER',
        p_source => q'[select * from orders where status = 'OPEN']'
      );
      wwv_flow_imp_page.create_page_item(
        p_id => 101,
        p_name => 'P10_ORDER_ID',
        p_source => 'P10_ORDER_ID'
      );
    end;
    """
    result = extract_export(source)
    assert result["summary"]["total_calls"] == 2
    assert result["summary"]["object_counts"] == {"PAGE": 1, "ITEM": 1}
    page = result["calls"][0]
    assert page["arguments"]["p_name"] == "Order, Header"
    assert "q'[select * from orders" in page["raw_arguments"]["p_source"]


def test_ignores_comments_and_string_contents() -> None:
    source = """
    -- wwv_flow_imp_page.create_page(p_id => 99);
    begin
      v_text := 'wwv_flow_imp_page.create_page(p_id => 88)';
      wwv_flow_imp_page.create_page(p_id => 1, p_name => 'Home');
    end;
    """
    result = extract_export(source)
    assert result["summary"]["total_calls"] == 1
    assert result["calls"][0]["arguments"]["p_id"] == 1


def test_reports_unterminated_call() -> None:
    result = extract_export("wwv_flow_imp_page.create_page(p_id => 1")
    assert result["diagnostics"][0]["code"] == "APEXEXP002"
