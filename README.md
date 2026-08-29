# specdbt

BDD-style `Given`/`When`/`Then` testing for dbt models and macros. Write a
scenario a stakeholder can read; specdbt runs it for real against dbt +
DuckDB and reports pass/fail.

## Why

dbt's own `unit_tests:` YAML is precise but write-only — nobody outside the
data team reads it, and its `given`/`expect` blocks don't read as a
sentence. specdbt scenarios are Gherkin: plain-English documentation of a
model's contract that also happens to be an executable test.

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
- Compiles model scenarios into native dbt `unit_tests:` YAML and runs them
  through `dbt test`, so you get dbt's own execution engine and error
  messages — not a reimplementation.
- Runs macro scenarios (e.g. `dbt_utils.generate_surrogate_key`) directly
  against a real DuckDB target, seeding fixtures and querying the compiled
  SQL.
- Reports results per scenario/step in a readable pass/fail summary.

`Given` rows can seed any source or model input; `@incremental_model` +
`input: this` scenarios can seed a model's own pre-existing state to test
its `is_incremental()` branch.

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
