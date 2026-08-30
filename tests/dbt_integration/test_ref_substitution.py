from specdbt.dbt_integration.ref_substitution import substitute_fixture_refs


def test_substitutes_ref_to_a_known_fixture_with_a_relation_object():
    result = substitute_fixture_refs("select * from {{ ref('orders') }}", "specdbt_abc", {"orders"})
    assert result == (
        "select * from {{ api.Relation.create(schema='specdbt_abc', identifier='orders') }}"
    )


def test_substitutes_ref_used_as_a_macro_argument():
    result = substitute_fixture_refs(
        "{{ dbt_utils.star(from=ref('orders')) }}", "specdbt_abc", {"orders"}
    )
    assert result == (
        "{{ dbt_utils.star(from=api.Relation.create(schema='specdbt_abc', identifier='orders')) }}"
    )


def test_substitutes_source_to_a_known_fixture():
    result = substitute_fixture_refs(
        "select * from {{ source('raw', 'orders') }}", "specdbt_abc", {"orders"}
    )
    assert result == (
        "select * from {{ api.Relation.create(schema='specdbt_abc', identifier='orders') }}"
    )


def test_leaves_ref_to_an_unknown_name_untouched():
    result = substitute_fixture_refs(
        "select * from {{ ref('real_model') }}", "specdbt_abc", {"orders"}
    )
    assert result == "select * from {{ ref('real_model') }}"


def test_leaves_a_call_with_no_ref_or_source_untouched():
    result = substitute_fixture_refs(
        "{{ dbt_utils.generate_surrogate_key(['a', 'b']) }}", "specdbt_abc", {"orders"}
    )
    assert result == "{{ dbt_utils.generate_surrogate_key(['a', 'b']) }}"


def test_substitutes_double_quoted_ref():
    result = substitute_fixture_refs('select * from {{ ref("orders") }}', "specdbt_abc", {"orders"})
    assert result == (
        "select * from {{ api.Relation.create(schema='specdbt_abc', identifier='orders') }}"
    )


def test_substitutes_ref_with_a_database_qualified_relation_when_database_is_given():
    result = substitute_fixture_refs(
        "select * from {{ ref('orders') }}", "specdbt_abc", {"orders"}, database="my_catalog"
    )
    assert result == (
        "select * from {{ api.Relation.create(database='my_catalog', schema='specdbt_abc', "
        "identifier='orders') }}"
    )
