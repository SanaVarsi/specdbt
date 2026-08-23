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
    assert "create schema if not exists specdbt_abc123" in text
    assert "create table specdbt_abc123.orders as (select 1)" in text
    assert "drop schema if exists specdbt_abc123 cascade" in text
    # each statement goes through set/endset then run_query(sql) -- not an
    # inlined double-quoted string -- so embedded {{ }} Jinja expressions in
    # a fixture CTAS (from render_sql_literal) don't break the outer syntax
    assert text.count("{% do run_query(sql) %}") == 3  # schema + 1 fixture + teardown


def test_write_and_delete_macro_file(tmp_path: Path):
    path = write_macro_file(tmp_path, "abc123", "-- content --")
    assert path == tmp_path / "macros" / "_specdbt_abc123.sql"
    assert path.read_text() == "-- content --"
    delete_macro_file(path)
    assert not path.exists()


def test_delete_macro_file_is_a_noop_if_already_gone(tmp_path: Path):
    delete_macro_file(tmp_path / "macros" / "does_not_exist.sql")  # must not raise
