from specdbt.dbt_integration.fixture_sql import render_fixture_ctas
from specdbt.fixtures import Fixture


def test_renders_ctas_with_casts_for_multiple_rows():
    fixture = Fixture(
        name="orders",
        rows=[
            {"order_id": 1, "status": "placed"},
            {"order_id": 2, "status": "shipped"},
        ],
    )
    sql = render_fixture_ctas("specdbt_abc123", fixture)
    assert sql == (  # noqa: E501
        "create table {{ api.Relation.create(schema='specdbt_abc123', identifier='orders') }} as (\n"  # noqa: E501
        "select {{ dbt.cast(1, dbt.type_bigint()) }} as order_id, "
        '{{ dbt.cast(dbt.string_literal(dbt.escape_single_quotes("placed")), dbt.type_string()) }} as status\n'  # noqa: E501
        "union all\n"
        "select {{ dbt.cast(2, dbt.type_bigint()) }} as order_id, "
        '{{ dbt.cast(dbt.string_literal(dbt.escape_single_quotes("shipped")), dbt.type_string()) }} as status\n'  # noqa: E501
        ")"
    )


def test_renders_ctas_for_a_single_row():
    fixture = Fixture(name="a", rows=[{"x": 1}])
    sql = render_fixture_ctas("s", fixture)
    assert sql == (
        "create table {{ api.Relation.create(schema='s', identifier='a') }} as (\n"
        "select {{ dbt.cast(1, dbt.type_bigint()) }} as x\n"
        ")"
    )


def test_column_order_follows_first_row_key_order():
    fixture = Fixture(name="a", rows=[{"b": 1, "a": 2}])
    sql = render_fixture_ctas("s", fixture)
    assert sql == (
        "create table {{ api.Relation.create(schema='s', identifier='a') }} as (\n"
        "select {{ dbt.cast(1, dbt.type_bigint()) }} as b, "
        "{{ dbt.cast(2, dbt.type_bigint()) }} as a\n"
        ")"
    )


def test_null_only_column_casts_to_string_type():
    fixture = Fixture(name="a", rows=[{"x": None}])
    sql = render_fixture_ctas("s", fixture)
    assert "{{ dbt.cast(NULL, dbt.type_string()) }} as x" in sql


def test_mixed_int_and_float_column_casts_to_float_type():
    fixture = Fixture(name="a", rows=[{"x": 1}, {"x": 2.5}])
    sql = render_fixture_ctas("s", fixture)
    assert "{{ dbt.cast(1, dbt.type_float()) }} as x" in sql
    assert "{{ dbt.cast(2.5, dbt.type_float()) }} as x" in sql


def test_mixed_str_and_int_column_casts_to_string_type():
    fixture = Fixture(name="a", rows=[{"x": 1}, {"x": "abc"}])
    sql = render_fixture_ctas("s", fixture)
    assert "{{ dbt.cast(1, dbt.type_string()) }} as x" in sql
    assert (
        '{{ dbt.cast(dbt.string_literal(dbt.escape_single_quotes("abc")), dbt.type_string()) }}'
        " as x" in sql
    )


def test_boolean_column_casts_to_boolean_type():
    fixture = Fixture(name="a", rows=[{"x": True}])
    sql = render_fixture_ctas("s", fixture)
    assert "{{ dbt.cast(TRUE, dbt.type_boolean()) }} as x" in sql


def test_database_kwarg_produces_a_catalog_qualified_relation():
    fixture = Fixture(name="a", rows=[{"x": 1}])
    sql = render_fixture_ctas("s", fixture, database="my_catalog")
    assert "api.Relation.create(database='my_catalog', schema='s', identifier='a')" in sql
