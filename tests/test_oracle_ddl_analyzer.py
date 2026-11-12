from apex2next_schema_analyzer import analyze_ddl


def test_inventories_common_oracle_ddl_objects() -> None:
    ddl = """
    CREATE TABLE app.orders (id NUMBER PRIMARY KEY, customer_id NUMBER REFERENCES app.customers(id));
    CREATE INDEX app.orders_ix1 ON app.orders(id);
    CREATE OR REPLACE PACKAGE BODY app.order_api AS
      PROCEDURE create_order IS BEGIN NULL; END;
    END;
    /
    CREATE SEQUENCE app.orders_seq;
    """
    result = analyze_ddl(ddl)
    assert result["summary"]["total_objects"] == 4
    assert result["summary"]["object_counts"]["TABLE"] == 1
    assert result["summary"]["object_counts"]["PACKAGE BODY"] == 1
    assert result["summary"]["object_counts"]["SEQUENCE"] == 1
    assert result["dependencies"][0]["target_object"] == "app.customers"


def test_ignores_create_text_inside_comments_and_strings() -> None:
    ddl = """
    -- CREATE TABLE fake_table (id NUMBER);
    CREATE TABLE real_table (note VARCHAR2(100) DEFAULT 'CREATE TABLE also_fake (x NUMBER)');
    """
    result = analyze_ddl(ddl)
    assert [obj["object_name"] for obj in result["objects"]] == ["real_table"]
