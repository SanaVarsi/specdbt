from specdbt.dbt_integration.relation_expr import relation_expr


def test_schema_and_identifier_without_database():
    assert relation_expr(schema="s", identifier="a") == (
        "api.Relation.create(schema='s', identifier='a')"
    )


def test_schema_identifier_and_database():
    assert relation_expr(schema="s", identifier="a", database="cat") == (
        "api.Relation.create(database='cat', schema='s', identifier='a')"
    )


def test_schema_only_relation_for_ddl():
    assert relation_expr(schema="s") == "api.Relation.create(schema='s')"


def test_schema_only_relation_with_database():
    assert relation_expr(schema="s", database="cat") == (
        "api.Relation.create(database='cat', schema='s')"
    )
