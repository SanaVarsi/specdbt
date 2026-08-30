# specdbt

BDD-style `Given`/`When`/`Then` testing for dbt models and macros. Write a
scenario a stakeholder can read; specdbt runs it for real against dbt +
DuckDB and reports pass/fail.

## Why

dbt's own `unit_tests:` YAML is precise but write-only — nobody outside the
data team reads it, and its `given`/`expect` blocks don't read as a
sentence. specdbt scenarios are Gherkin: plain-English documentation of a
model's contract that also happens to be an executable test.

Macros are worse off: **dbt has no native way to unit test a macro at all**
([dbt-core#10547](https://github.com/dbt-labs/dbt-core/issues/10547), still
open). If you use `dbt_utils.generate_surrogate_key`, `dbt_utils.star`, or
any custom macro, there's no built-in mechanism to pin down its behavior —
you either test it indirectly through a model or don't test it. specdbt
gives macros the same BDD interface as models and runs them for real, which
covers a gap dbt itself doesn't.

```gherkin
Feature: stg_customers renames the raw seed's id column

  Scenario: Renames id to customer_id, passes names through unchanged
    Given the following rows in "raw_customers":
      | id | first_name | last_name |
      | 1  | Michael    | P.        |
    When the "stg_customers" model runs
    Then the "stg_customers" should produce the following rows:
      | customer_id | first_name | last_name |
      | 1           | Michael    | P.        |
```

Run it, and specdbt compiles it into a real dbt unit test, executes it
against your actual model SQL, and reports the result — no hand-maintained
YAML, no hardcoded expected output.

## What it does

- Parses `.feature` files (standard Gherkin, no custom dialect).
- **Model scenarios (`@unit`, the default for a `When the "<model>" model
  runs` step):** compiles the scenario's Given/Then straight into a real
  dbt `unit_tests:` YAML entry and runs it via `dbt test` — you get dbt's
  own fixture injection, type-casting, and diffing, not a reimplementation.
- **Macro scenarios (`@integration`, the default for a `When the "<macro
  call>" macro runs` step):** since dbt has no native mechanism for this,
  specdbt seeds `Given` fixtures as real ephemeral tables and runs the
  macro's actual Jinja/SQL through `dbt show --inline` against a real
  DuckDB target, then tears the ephemeral state down.
- Incremental models: tag a scenario `@incremental_model`; adding `And the
  following rows already in "<model>":` runs it against the
  `is_incremental()` branch, omitting it runs the full-refresh branch.
- Reports results per scenario/step in a readable pass/fail summary.

## Quickstart

```bash
uv sync
uv run specdbt init features/       # scaffold an example .feature file
uv run specdbt run features/        # parse, run, report
```

`specdbt run` needs a real dbt project to execute against — see below for
a working example.

## Run it against a real dbt project

```bash
uv run specdbt run examples/jaffle_shop/features \
  --engine dbt \
  --project-dir examples/jaffle_shop \
  --profiles-dir examples/jaffle_shop/profiles
```

This runs `stg_customers`, `customers`, and `order_history` (including
both branches of an `is_incremental()` model) against a real DuckDB
target built from `dbt-labs/jaffle-shop-classic`.

`examples/dbt_utils_macros/` shows the same thing for macro scenarios —
`dbt_utils.generate_surrogate_key` and `dbt_utils.star` run against real
fixtures:

```bash
cd examples/dbt_utils_macros && uv run dbt deps --profiles-dir profiles
uv run specdbt run examples/dbt_utils_macros/features \
  --engine dbt \
  --project-dir examples/dbt_utils_macros \
  --profiles-dir examples/dbt_utils_macros/profiles
```

`--engine fake` (the default) skips dbt entirely: each `.feature` file may
have a co-located `.canned.py` exposing `CANNED_RESULTS`, useful for
testing specdbt itself or prototyping a scenario's shape before wiring up
a real model.

## Writing scenarios

See `docs/gherkin-style-guide.md` for the full style guide. The short
version:

- Write scenarios declaratively (state the contract, not the steps a
  human would click through).
- Name scenarios by business behavior, not mechanism.
- Data tables (`the following rows in "<x>":`) are the default way to
  express fixtures and expected output.
- Tag a scenario `@unit` or `@integration` only when the default (model →
  unit, macro → integration) is wrong for that scenario.
- Tag every scenario on an incremental model `@incremental_model` — it
  states a fact about the model, not just the scenarios that need
  `input: this`.

## Development

```bash
uv run pytest       # test suite
uv run ruff check .
uv run ruff format .
```

The test suite includes end-to-end tests that run the real examples
through the real CLI (`tests/test_examples_jaffle_shop.py`,
`tests/test_examples_dbt_utils_macros.py`) — a green suite means the
examples above actually work, not just that unit tests pass.

### Testing against other adapters

The default `uv run pytest` above only exercises DuckDB. The macro tier's
adapter-dispatch code (spec:
`docs/superpowers/specs/2026-08-30-macro-tier-adapter-dispatch-design.md`)
has two more adapter-specific test files, both skipped unless you opt in —
neither is required for the default suite to pass.

**Postgres** (runnable locally, and CI-verified):

1. Create a `.env` file (gitignored) in the repo root with three lines —
   pick any values for the two that say "your choice":
   - `POSTGRES_USER` — your choice, e.g. `specdbt`
   - `POSTGRES_PASSWORD` — your choice
   - `POSTGRES_DB` — your choice, e.g. `specdbt_test`
2. Start it: `docker compose up -d postgres`
3. Export the *same three values* under the names the test reads, plus two
   fixed ones, then run the test:
   ```bash
   export SPECDBT_PG_USER=<your POSTGRES_USER value>
   export SPECDBT_PG_SECRET=<your POSTGRES_PASSWORD value>
   export SPECDBT_PG_DBNAME=<your POSTGRES_DB value>
   export SPECDBT_PG_HOST=localhost SPECDBT_PG_PORT=5432 SPECDBT_TEST_POSTGRES=1
   uv run pytest tests/test_dbt_adapter_postgres.py -v
   ```
   (Two names per value because `.env`/docker-compose need Postgres's own
   env var names, while the test — like any Python code — just reads
   `os.environ`, not `.env`, so the same values need exporting under the
   names it actually looks for: `tests/conftest.py`.)

**Databricks** (manual, needs your own workspace — no CI, no local
default): see `docs/databricks-validation-checklist.md`.

## Contributing

Issues, ideas, and PRs are welcome. The `ExecutionAdapter` interface
(`src/specdbt/adapters/base.py`) is the extension point for a new backend
(a different warehouse, a different execution engine) — one new class, not
a rewrite.

Known limitations, by design:
- `specdbt run` executes whatever's in a `.feature` file's `.canned.py`
  companion (`--engine fake`) or compiles and runs real dbt SQL
  (`--engine dbt`) — don't run it against scenarios you haven't reviewed,
  the same way you wouldn't run an unreviewed `conftest.py`.
- The step-by-step summary counts only steps that were actually
  attempted — a scenario that fails partway through under-reports its
  remaining steps as "not there" rather than explicitly "skipped."

## License

MIT — see `LICENSE`.
