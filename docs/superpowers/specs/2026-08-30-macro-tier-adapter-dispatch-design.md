# Cross-Adapter Correctness for the Macro/Integration Tier (Databricks + DuckDB + others)

## Context

specdbt's macro/integration testing tier (`src/specdbt/dbt_integration/`) drives real dbt
execution to test macros against ephemeral fixture data. It has only ever been validated
against DuckDB. The model unit-tier (native `unit_tests:` YAML) is already adapter-agnostic
by construction — it emits pure dbt-native YAML and lets dbt-core's own per-adapter test
runner generate 100% of the SQL, so it needs no changes and is out of scope here.

The user's ask, refined over discussion: don't just patch around Databricks specifically —
understand *why* the model tier is already generic and the macro tier isn't, and fix the macro
tier the same way, so the "create fixture tables in a scratch schema → run the macro → compare
→ drop schema" pattern becomes genuinely engine-generic (DuckDB, Databricks, Snowflake,
Postgres, whatever a project's profile points at) rather than DuckDB-shaped.

No Databricks credentials exist to validate against live, so this plan is designed to be
verified via unit tests, dbt-core's own relation/dispatch mechanisms directly, and (optionally)
a second local adapter as a CI smoke test — not a live Databricks run.

## How dbt's adapter dispatch layer actually works (and why it's the answer)

A common misconception worth correcting explicitly, since it shapes the whole design: **Jinja
is not what makes dbt SQL portable.** Jinja is just the templating language every macro is
written in — it has no idea what a "schema" or a "cast" is. The actual cross-engine mechanism
is dbt-core's **adapter macro dispatch**:

- A macro calls `{{ adapter.dispatch('macro_name', 'packagenamespace')(args) }}`.
- At **parse/compile time** (not runtime), dbt-core looks for an implementation named
  `<active_adapter_type>__macro_name` first (e.g. `databricks__macro_name`,
  `duckdb__macro_name`), and falls back to `default__macro_name` if the active adapter has no
  override. "Active adapter type" is whatever adapter plugin is loaded for the project's
  current `--target` — decided per invocation, not baked into the macro.
- dbt-core ships a large library of portable macros built exactly this way — `dbt.cast(...)`,
  `dbt.type_string()`, `dbt.type_float()`, `dbt.string_literal(...)`, `dbt.escape_single_quotes(...)`
  — each with a `default__` implementation plus adapter-specific overrides only where a
  dialect genuinely differs. `dbt_utils` (and adapter packages like `dbt-labs/spark_utils`)
  extend the same pattern for higher-level macros (`generate_surrogate_key`, `star`, etc.).
- Separately, `adapter.create_schema(relation)` / `adapter.drop_schema(relation)` /
  `adapter.get_columns_in_relation(relation)` are Python methods on `BaseAdapter` itself
  (marked `@available`, which is what exposes a Python adapter method to the Jinja `adapter`
  global) — not macros, but the same principle: each adapter subclass implements the DDL for
  its own dialect, and calling the method lets dbt-core pick the right one.

**Consequence**: a macro is portable exactly to the degree it's built from dispatch-based
primitives instead of raw engine-specific SQL. This is a property of *how something is
written*, decided once by dbt-core/package authors, resolved fresh per invocation based on
whichever adapter is active — never something a test harness can inject after the fact.

**Why the model unit-tier is free and the macro tier isn't**: for models, dbt-core has a native
`unit_tests:` mechanism — dbt-core's own generator writes 100% of the fixture SQL, using
`dbt.cast`/type macros/`get_columns_in_relation` internally already. specdbt just emits YAML;
dbt-core does the dispatch-aware SQL generation. For macros, **dbt-core has no native testing
mechanism at all** (confirmed: referenced in the codebase as dbt-core issue #10547) — so
specdbt has to build the fixture/run/compare/teardown plumbing itself, and today that plumbing
writes raw SQL strings instead of going through dispatch. That's the entire gap: not the
*pattern*, which is exactly what dbt-core's own unit-test generator does internally anyway, but
the fact that in 3 specific spots, **specdbt is currently the one writing non-dispatched SQL**
instead of dbt-core.

**Orchestration is already generic, confirmed in code**: `DbtExecutionAdapter.__init__` already
accepts `target: str | None` and every `_invoke()` call passes `--target` through to
`dbtRunner` (`src/specdbt/adapters/dbt_adapter.py:48,100-101`). Pointing a test run at a
Databricks target — or any target a project's `profiles.yml` defines — already works
mechanically today; a CI matrix over engines is just "run the suite once per `--target`," no
new orchestration to build. The only work is making the 3 SQL-writing spots inside that
already-generic flow use dispatch instead of hand-rolled text.

**Hard boundary, stated plainly**: if the macro-under-test itself calls a non-dispatched,
engine-specific SQL function, no framework — specdbt or `dbt run` itself — can make it
portable. dbt makes portability *available* to macros that use its abstraction layer; it can't
retrofit ones that don't. This plan closes specdbt's own gap, not the user's macro-authoring
choices.

## The three gaps, and the dispatch-based fix for each

### 1. Schema create/drop (`macro_file.py`)

**Today**: literal strings — `f"create schema if not exists {schema}"` /
`"drop schema if exists {schema} cascade"` — embedded via `{% set sql %}...{% endset %}` +
`{% do run_query(sql) %}`.

**Fix**: replace with `{% do adapter.create_schema(relation) %}` /
`{% do adapter.drop_schema(relation) %}`, where `relation` is an `api.Relation.create(schema=...,
database=<resolved catalog>)` (catalog resolution — see gap 3). These `BaseAdapter` methods
already dispatch to each adapter's correct DDL, with connection-commit and relation-cache
handling included for free. Composes directly inside the existing macro block — no change to
the `{% set sql %}` CTAS pattern needed alongside it.

**DuckDB safety**: DuckDB has no override, so it falls through to the same effective SQL as
today (`create schema if not exists <relation>`).

### 2. Fixture CTAS (`fixture_sql.py`)

**Today**: a `VALUES (...) AS t(col1, col2)` table constructor with column types purely
inferred by the warehouse from literal values — no explicit cast, no adapter dispatch. This is
the highest cross-engine risk: `VALUES`-clause type inference (an all-NULL column, mixed
int/float precision, date-like strings) is not guaranteed identical across engines, since it's
each engine's own literal-inference behavior, not something dbt's dispatch layer touches at
all today.

**Fix**: keep column types Python-value-derived (still the only information available — many
fixture names aren't real manifest nodes, so `get_columns_in_relation` isn't usable for the
common case), but make the type explicit and dispatch-resolved instead of implicit:
- Per column, pick one dbt type macro from the coerced values present: `dbt.type_float()` if
  any float, else `dbt.type_bigint()` if any int, else `dbt.type_boolean()` if any bool, else
  `dbt.type_string()` (also the default for an all-NULL column).
- Wrap each literal with `dbt.cast(<literal>, <type_macro>)` — **`dbt.cast`, not
  `dbt.safe_cast`**: some adapters implement `safe_cast` as a silently-`NULL`-on-failure
  `try_cast`, which is exactly wrong for a testing framework (a fixture/type mismatch should
  error loudly, not silently produce a wrong row).
- Emit `create table {{ relation }} as (select <casts> union all select <casts> ...)` —
  matching the shape dbt-core's own native unit-test fixture generator uses internally —
  instead of a `VALUES (...) AS t(cols)` constructor, avoiding cross-engine column-aliasing and
  implicit-coercion quirks.
- Target relation built via `api.Relation.create(schema=..., identifier=..., database=<resolved
  catalog>)`, not a hand-written `f"{schema}.{fixture.name}"` string.

This is the change with the most DuckDB-regression surface (agate's Python-type inference from
`dbt show` results could shift), so it's implemented and regression-tested last, with new
fixtures added for a NULL-only column, mixed int/float, and all-string.

### 3. `ref()`/`source()` substitution (`ref_substitution.py`)

**Today**: `api.Relation.create(schema='...', identifier='...')` — no catalog component. On
Unity Catalog Databricks (3-level `catalog.schema.table` addressing), this silently resolves
against the session's default catalog instead of the project's configured one — a real
correctness gap whenever a project deliberately targets a non-default catalog.

**Fix**: resolve the target catalog **once per `run_macro()` call**, from the raw resolved
profile target dict — check for a `catalog` key first (Databricks/Snowflake spelling), fall
back to `database`/`dbname` only if present, else `None`. This is read from the raw YAML dict,
not a parsed `Credentials` dataclass — `dbt-duckdb`'s own `Credentials.database` defaults to
the literal `"main"`, so reading the dataclass directly would silently turn every existing
DuckDB relation 3-part. Working off the raw profile dict makes today's DuckDB `None` result
fall out "by construction" (neither example project's profile declares `catalog`/`database`),
not from an adapter-type special case.

Add a keyword-only `database: str | None = None` param to `substitute_fixture_refs`. `None` →
emit exactly today's text (no `database=` kwarg at all, keeping all 6 existing tests passing
unchanged). Set → emit `api.Relation.create(database='...', schema='...', identifier='...')`.

**One resolved value threads through all three gaps** — the schema relation (create + drop),
every fixture's CTAS target relation, and every substituted `ref()`/`source()` relation must
agree on catalog, or fixtures land in one catalog while the macro's own refs resolve to
another. This becomes an explicit cross-tier test (item 4 below).

## Suggested implementation order

1. Catalog-resolution helper (pure, independent of the other two).
2. Schema create/drop — smallest, most mechanical, immediately provable against DuckDB.
3. `ref`/`source` substitution — depends on the resolved catalog value.
4. Fixture CTAS — largest surface, biggest DuckDB-regression risk; do last, full regression run
   after each step, not just at the end.

## Critical files

- `src/specdbt/dbt_integration/macro_file.py` — schema create/drop → `adapter.create_schema`/`drop_schema`
- `src/specdbt/dbt_integration/fixture_sql.py` — CTAS → explicit `dbt.cast`+type macros, `union all select`
- `src/specdbt/dbt_integration/ref_substitution.py` — new `database` param
- `src/specdbt/adapters/dbt_adapter.py` — resolve catalog once in `run_macro`, thread through
- New: small catalog-resolution helper (e.g. `dbt_integration/target_catalog.py`)
- Tests: `tests/dbt_integration/test_macro_file.py`, `test_fixture_sql.py`,
  `test_ref_substitution.py`, `tests/test_dbt_adapter.py` — existing exact-string assertions
  need deliberate updates (expected, not regressions); new tests added per above.

## Verification (no live Databricks access)

1. **Full existing suite** (157 tests) passes after each of the 4 steps, not just at the end.
2. **Catalog-resolution helper**: unit tests against fixture profile YAMLs — no `catalog`/
   `database` key → `None`; `catalog: my_catalog` → `"my_catalog"`; `catalog:
   "{{ env_var('DBT_CATALOG') }}"` → confirms Jinja rendering. No live connection needed.
3. **Relation-shape tests**: construct `api.Relation.create(database=..., ...)` directly via
   dbt-core (installed, no live adapter needed) and assert 2-part vs. 3-part `.render()` output
   for `database=None` vs. a real value — validates the mechanism Unity Catalog needs, using
   dbt-core's own code, not a guess at Databricks syntax.
4. **Cross-tier invariant test** (real DuckDB scratch project, as tests run today): one
   `run_macro()` call, assert the schema relation, fixture CTAS relation, and substituted
   `ref()` relation all agree on catalog — catches "schema in A, tables in B" bugs on the one
   adapter actually available in CI.
5. **`--target` matrix as the multi-engine story**: no new orchestration needed — CI adds a
   second (or third) `profiles.yml` target and runs the existing specdbt CLI once per target,
   exactly the pattern any dbt project already uses for dev/ci/prod.

6. **Postgres as a real second adapter — firm requirement, not optional**: add `dbt-postgres` as
   a dev dependency and a local Postgres service (docker-compose, or a testcontainer) to CI.
   Add a second `profiles.yml` target (`type: postgres`) to at least the `jaffle_shop` and
   `dbt_utils_macros` example projects, with `database`/`dbname` set to a real, non-default
   value so the catalog-threading fix (gap 3) is genuinely exercised, not just DuckDB's
   degenerate 2-part case. Run the full macro-tier suite against Postgres as part of this
   plan's own verification, before considering the work done — this is the actual empirical
   check for all three gaps end-to-end on a non-DuckDB engine, since Postgres is installable
   and runnable in CI today. Confirm at implementation time whether `dbt-postgres` renders
   2- or 3-part relations by default and record the answer in the spec/tests either way.

7. **Databricks — user-driven manual validation, not CI-gated**: no Databricks credentials
   exist in this environment; the user intends to get a Databricks Community Edition (or trial)
   workspace to validate separately. To make that validation cheap when it happens: keep the
   catalog-resolution helper's `catalog`/`database` key-reading generic (already the design —
   nothing Databricks-specific to wire in ahead of time), and write a short manual checklist
   (a `docs/` note, not a CI job) covering: create a `profiles.yml` target with `type:
   databricks` and a `catalog:` set to a non-default Unity Catalog catalog, run the existing
   example projects' macro-tier scenarios against it, and confirm schema/fixture/ref relations
   all land in the configured catalog. Add an optional `@requires_databricks`-marked test
   (skipped by default, no `DATABRICKS_*` env vars required to run the rest of the suite) that
   the user can enable once they have a workspace — this is the honest final confidence step,
   not something CI claims to prove on its own.

## Status

Approved. Next step: writing-plans skill produces a step-by-step implementation plan from this
design.
