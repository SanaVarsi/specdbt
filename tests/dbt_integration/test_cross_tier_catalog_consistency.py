"""Gap 1/2/3 of the macro-tier adapter-dispatch design (spec, 2026-08-30)
must all resolve the same catalog for one run, or fixtures land in one
catalog while the macro's own refs resolve to another. This is a pure
text-level check -- no live non-DuckDB catalog is testable in this repo
(Postgres can't address a second catalog cross-database; no Databricks
credentials exist, see test_dbt_adapter_databricks.py)."""

from specdbt.dbt_integration.fixture_sql import render_fixture_ctas
from specdbt.dbt_integration.macro_file import render_macro_file
from specdbt.dbt_integration.ref_substitution import substitute_fixture_refs
from specdbt.fixtures import Fixture


def test_schema_fixture_and_ref_relations_agree_on_catalog():
    database = "my_catalog"
    schema = "specdbt_abc123"
    fixture = Fixture(name="orders", rows=[{"id": 1}])

    macro_text = render_macro_file("abc123", schema, [], database=database)
    fixture_sql = render_fixture_ctas(schema, fixture, database=database)
    substituted = substitute_fixture_refs(
        "select * from {{ ref('orders') }}", schema, {"orders"}, database=database
    )

    schema_relation = f"api.Relation.create(database='{database}', schema='{schema}')"
    full_relation = (
        f"api.Relation.create(database='{database}', schema='{schema}', identifier='orders')"
    )
    assert schema_relation in macro_text
    assert full_relation in fixture_sql
    assert full_relation in substituted


def test_schema_fixture_and_ref_relations_agree_when_no_catalog_is_configured():
    schema = "specdbt_abc123"
    fixture = Fixture(name="orders", rows=[{"id": 1}])

    macro_text = render_macro_file("abc123", schema, [])
    fixture_sql = render_fixture_ctas(schema, fixture)
    substituted = substitute_fixture_refs("select * from {{ ref('orders') }}", schema, {"orders"})

    assert f"api.Relation.create(schema='{schema}')" in macro_text
    assert f"api.Relation.create(schema='{schema}', identifier='orders')" in fixture_sql
    assert f"api.Relation.create(schema='{schema}', identifier='orders')" in substituted
