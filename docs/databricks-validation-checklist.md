# Databricks Validation Checklist

No Databricks credentials exist in this repo's CI or dev environment, so
cross-catalog addressing (Unity Catalog's `catalog.schema.table`) is
verified structurally (unit tests, `test_cross_tier_catalog_consistency.py`)
but not against a real Databricks workspace. When you have access to one
(e.g. Databricks Community Edition or a trial workspace):

1. Set the environment variables `test_dbt_adapter_databricks.py` reads
   (host, HTTP path, connection secret, catalog, schema — see that file's
   `scratch_dbt_project_databricks` fixture for the exact names), pointing
   at a target with a **non-default** Unity Catalog catalog.
2. Run: `uv run pytest tests/test_dbt_adapter_databricks.py -v`
3. Confirm the scenario passes and that no tables/schemas are left behind
   in the configured catalog afterward (check via the Databricks UI or
   `SHOW SCHEMAS IN <catalog> LIKE 'specdbt_%'`).
4. Optionally, run the `jaffle_shop`/`dbt_utils_macros` example projects'
   macro-tier scenarios (`examples/*/features/*.feature`) against the same
   target, by adding a `databricks` output to their `profiles.yml` and
   passing `--target databricks` to the specdbt CLI.
5. Report back which relation shape (2- or 3-part) `dbt-databricks`
   produced for the catalog-qualified case, same as Task 10 did for
   Postgres, so the design spec's open item can be closed.
