from specdbt.dbt_integration.fixture_sql import render_fixture_ctas
from specdbt.fixtures import Fixture


def test_renders_ctas_with_values_for_multiple_rows():
    fixture = Fixture(
        name="orders",
        rows=[
            {"order_id": 1, "status": "placed"},
            {"order_id": 2, "status": "shipped"},
        ],
    )
    sql = render_fixture_ctas("specdbt_abc123", fixture)
    assert sql == (
        "create table specdbt_abc123.orders as ("
        "select * from (values "
        '(1, {{ dbt.string_literal(dbt.escape_single_quotes("placed")) }}), '
        '(2, {{ dbt.string_literal(dbt.escape_single_quotes("shipped")) }})'
        ") as t(order_id, status))"
    )


def test_renders_ctas_for_a_single_row():
    fixture = Fixture(name="a", rows=[{"x": 1}])
    sql = render_fixture_ctas("s", fixture)
    assert sql == "create table s.a as (select * from (values (1)) as t(x))"


def test_column_order_follows_first_row_key_order():
    fixture = Fixture(name="a", rows=[{"b": 1, "a": 2}])
    sql = render_fixture_ctas("s", fixture)
    assert "as t(b, a)" in sql
    assert "(1, 2)" in sql
