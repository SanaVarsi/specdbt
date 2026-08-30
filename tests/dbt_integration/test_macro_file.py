from pathlib import Path

from specdbt.dbt_integration.macro_file import (
    delete_macro_file,
    render_macro_file,
    setup_macro_name,
    teardown_macro_name,
    write_macro_file,
)


def test_macro_names_are_derived_from_run_id():
    assert setup_macro_name("abc123") == "_specdbt_abc123_setup"
    assert teardown_macro_name("abc123") == "_specdbt_abc123_teardown"


def test_render_macro_file_contains_setup_and_teardown_macros():
    text = render_macro_file(
        "abc123",
        "specdbt_abc123",
        ["create table specdbt_abc123.orders as (select 1)"],
    )
    assert "{% macro _specdbt_abc123_setup() %}" in text
    assert "{% macro _specdbt_abc123_teardown() %}" in text
    assert "{% do adapter.create_schema(api.Relation.create(schema='specdbt_abc123')) %}" in text
    assert "{% do adapter.drop_schema(api.Relation.create(schema='specdbt_abc123')) %}" in text
    assert "create table specdbt_abc123.orders as (select 1)" in text
    # schema create/drop now go through adapter.create_schema/drop_schema
    # directly (dispatch-resolved per adapter, spec: macro-tier
    # adapter-dispatch design) -- only the fixture CTAS still goes through
    # set/endset + run_query(sql), so embedded {{ }} Jinja expressions in a
    # fixture CTAS (from sql_literal_expr) don't break the outer syntax
    assert text.count("{% do run_query(sql) %}") == 1


def test_render_macro_file_with_database_qualifies_the_schema_relation():
    text = render_macro_file("abc123", "specdbt_abc123", [], database="my_catalog")
    assert (
        "{% do adapter.create_schema(api.Relation.create(database='my_catalog', "
        "schema='specdbt_abc123')) %}" in text
    )
    assert (
        "{% do adapter.drop_schema(api.Relation.create(database='my_catalog', "
        "schema='specdbt_abc123')) %}" in text
    )


def test_write_and_delete_macro_file(tmp_path: Path):
    path = write_macro_file(tmp_path, "abc123", "-- content --")
    assert path == tmp_path / "macros" / "_specdbt_abc123.sql"
    assert path.read_text() == "-- content --"
    delete_macro_file(path)
    assert not path.exists()


def test_delete_macro_file_is_a_noop_if_already_gone(tmp_path: Path):
    delete_macro_file(tmp_path / "macros" / "does_not_exist.sql")  # must not raise
