---
type: Module
title: dbt_integration/ — Macro-Tier Adapter Dispatch
description: The plumbing DbtExecutionAdapter.run_macro() uses to execute a macro for real against any dbt-supported warehouse.
tags: [module, dbt-integration, macro-tier]
---

# dbt_integration/ — Macro-Tier Adapter Dispatch

Supports the integration tier's macro execution (see
[Two-Tier Design](two-tier-design.md) and [Adapters](adapters.md)).
Adapter-dispatch based — not hardcoded to one warehouse's SQL dialect —
so it works across dbt's supported adapters (DuckDB, Postgres,
Databricks, ...).

- `macro_file.py` — builds the temporary `.sql` file that wraps the macro
  call for `dbt show --inline`. `setup_macro_name(run_id)` /
  `teardown_macro_name(run_id)` name the ephemeral schema's setup/teardown
  macros; `render_macro_file(...)` renders the file content;
  `write_macro_file(project_dir, run_id, content) -> Path` writes it;
  `delete_macro_file(path)` cleans it up. Schema create/drop goes through
  `adapter.create_schema`/`drop_schema` — not raw SQL — so it works on
  every dbt adapter.
- `fixture_sql.py::render_fixture_ctas(schema, fixture, *, database=None)`
  renders a `CREATE TABLE ... AS SELECT ... UNION ALL ...` for a
  `Fixture`, with each cell wrapped in a `dbt.cast(val, <type macro>)`
  call chosen by `_dbt_type_macro(values)` — this is what makes fixture
  loading cross-database rather than DuckDB-specific.
- `ref_substitution.py::substitute_fixture_refs(...)` regex-swaps
  `ref()`/`source()` calls in the macro-call text for
  `api.Relation.create(...)` calls pointing at the ephemeral schema.
- `relation_expr.py::relation_expr(...)` — shared Relation-text builder
  used by both `fixture_sql.py` and `ref_substitution.py`, so the two
  never drift on how a relation reference is rendered.
- `target_catalog.py::resolve_target_catalog(project_dir, profiles_dir,
  target) -> str | None` resolves the target's `catalog`/`database`/
  `dbname` from the raw dbt profile dict, once per run.

`DbtExecutionAdapter.run_macro()` resolves the catalog once via
`target_catalog.py` and threads that single value through
`fixture_sql.py` and `ref_substitution.py`, so every rendered SQL
statement in one run agrees on which catalog/database it targets.
