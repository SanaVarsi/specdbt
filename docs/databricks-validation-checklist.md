# Databricks Validation Checklist

No Databricks credentials exist in this repo's CI or dev environment, so
cross-catalog addressing (Unity Catalog's `catalog.schema.table`) is
verified structurally (unit tests, `test_cross_tier_catalog_consistency.py`)
but not against a real Databricks workspace. When you have access to one
(e.g. Databricks Community Edition or a trial workspace):

1. Install `dbt-databricks` into your local environment — it is not a
   project dependency (unlike `dbt-postgres`, which is a permanent `dev`
   dependency-group entry in `pyproject.toml`; Databricks credentials
   aren't available in this repo's CI or dev environment, so this install
   is a one-off, local-only step for a manual validation run, e.g.
   `uv add --dev dbt-databricks` and then revert that `pyproject.toml`
   change afterward, or install into the venv directly without touching
   `pyproject.toml`). Without it, the test fails with an unknown adapter
   type even given valid credentials.
2. Set the environment variables `test_dbt_adapter_databricks.py`'s
   `scratch_dbt_project_databricks` fixture reads: `DATABRICKS_HOST`,
   `DATABRICKS_HTTP_PATH`, `DATABRICKS_CONN_SECRET` (all required), plus
   optional `DATABRICKS_CATALOG` (default `main`) and `DATABRICKS_SCHEMA`
   (default `default`) — pointing at a target with a **non-default** Unity
   Catalog catalog.
3. Run: `uv run pytest tests/test_dbt_adapter_databricks.py -v`
4. Confirm the scenario passes and that no tables/schemas are left behind
   in the configured catalog afterward (check via the Databricks UI or
   `SHOW SCHEMAS IN <catalog> LIKE 'specdbt_%'`).
5. Optionally, run the `jaffle_shop` example project's scenarios
   (`examples/jaffle_shop/features/` — both unit-tier models and
   integration-tier macros) against the same target, by adding a
   `databricks` output to its `profiles.yml` and passing `--target
   databricks` to the specdbt CLI.
6. Report back which relation shape (2- or 3-part) `dbt-databricks`
   produced for the catalog-qualified case, same as Task 10 did for
   Postgres, so the design spec's open item can be closed.
