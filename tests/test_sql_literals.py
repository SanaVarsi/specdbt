from specdbt.sql_literals import render_sql_literal


def test_renders_none_as_null():
    assert render_sql_literal(None) == "NULL"


def test_renders_true_and_false():
    assert render_sql_literal(True) == "TRUE"
    assert render_sql_literal(False) == "FALSE"


def test_renders_int_and_float_as_raw_literals():
    assert render_sql_literal(42) == "42"
    assert render_sql_literal(18.2) == "18.2"
    assert render_sql_literal(-5) == "-5"


def test_renders_plain_string():
    assert render_sql_literal("brightsky") == (
        '{{ dbt.string_literal(dbt.escape_single_quotes("brightsky")) }}'
    )


def test_escapes_single_quote_for_the_sql_layer_via_dbt_own_macros():
    # Correctness of the *SQL-level* escape (' -> '') is dbt's own job, via
    # escape_single_quotes -- verified empirically against a real dbt-duckdb
    # target in test_dbt_adapter.py::test_run_macro_handles_string_values_with_quotes.
    # This test only pins the *text* specdbt generates.
    assert render_sql_literal("O'Brien") == (
        '{{ dbt.string_literal(dbt.escape_single_quotes("O\'Brien")) }}'
    )


def test_escapes_double_quote_and_backslash_for_the_jinja_argument_itself():
    assert render_sql_literal('say "hi"') == (
        '{{ dbt.string_literal(dbt.escape_single_quotes("say \\"hi\\"")) }}'
    )
    assert render_sql_literal("back\\slash") == (
        '{{ dbt.string_literal(dbt.escape_single_quotes("back\\\\slash")) }}'
    )
