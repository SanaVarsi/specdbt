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

With [`just`](https://github.com/casey/just#installation):
```bash
just setup                # uv sync + pre-commit install
just init features/       # scaffold an example .feature file
just run features/        # parse, run, report
```

Without it:
```bash
uv sync
uv run specdbt init features/       # scaffold an example .feature file
uv run specdbt run features/        # parse, run, report
```

`specdbt run` needs a real dbt project to execute against — see below for
a working example.

## Installing specdbt in your dbt project

specdbt is a dev-time test runner, not a runtime dependency of your dbt
project — add it to your project's dev tooling, then point it at the
project and profile you already have.

```bash
uv add --dev specdbt          # or: pip install specdbt
```

specdbt has no per-warehouse code of its own: both tiers execute through
real `dbt` (`dbtRunner`/`dbt test`) against whatever `profiles.yml`
target you already use, and the macro tier's fixture/ref plumbing rides
dbt-core's own adapter-dispatch — so **any warehouse dbt-core supports is
in scope**. Add that warehouse's dbt adapter alongside specdbt, using the
matching extra where one exists:

```bash
uv add --dev "specdbt[databricks]"   # pulls in dbt-databricks
uv add --dev "specdbt[snowflake]"    # pulls in dbt-snowflake
uv add --dev "specdbt[postgres]"     # pulls in dbt-postgres
# DuckDB (dbt-duckdb) ships as a specdbt dependency already -- no extra needed
```
No extra for your warehouse? Add its `dbt-<adapter>` package directly —
extras are a convenience, not a requirement.

Then run it exactly like any other dbt invocation, against your existing
project:

```bash
uv run specdbt run features/ \
  --engine dbt \
  --project-dir . \
  --profiles-dir ~/.dbt \
  --target <your target name>
```
(`--project-dir` is required with `--engine dbt`; `--profiles-dir`
defaults to `--project-dir` if omitted.)

Validation status, so you know what's actually been run against a real
target in this repo vs. what's expected to work by design:
- **DuckDB** — the default, CI-verified on every commit.
- **Postgres** — CI-verified (`gitleaks`-safe `.env`, see Development
  below).
- **Databricks** — manually validated against a real workspace; see
  `docs/knowledge/databricks-validation-checklist.md` for the steps and
  its one open item (2- vs. 3-part relation naming for catalog-qualified
  refs).
- **Snowflake and others** — untested in this repo (no credentials, no
  checklist yet), but nothing in the design is Postgres/Databricks-
  specific — if you run it against one, a PR adding a checklist like
  Databricks' is welcome.

## Run it against a real dbt project

```bash
just run-example
```
equivalent to:
```bash
cd examples/jaffle_shop && uv run dbt deps --profiles-dir profiles && cd ../..
uv run specdbt run examples/jaffle_shop/features \
  --engine dbt \
  --project-dir examples/jaffle_shop \
  --profiles-dir examples/jaffle_shop/profiles
```

This runs models (`stg_customers`, `customers`, `order_history` — including
both branches of an `is_incremental()` model, and `order_surrogate_keys`,
which consumes a `dbt_utils` macro inside a model) at the unit tier, and
macros standalone at the integration tier — `dbt_utils.generate_surrogate_key`/
`dbt_utils.star`, plus three of the project's own (`macros/`):
`bucket_order_value` (conditional tiering), `pivot_sum` (a parameterized
Jinja for-loop generalizing the hardcoded loop in `orders.sql`), and
`order_value_summary` (composes `bucket_order_value`) — all against a
real DuckDB target built from `dbt-labs/jaffle-shop-classic` plus
`dbt-labs/dbt_utils`. One project covers both tiers, since tier is a
per-scenario default (model → unit, macro → integration), not a
per-project setting.

Scenarios are organized `features/{macros,models}/<name>/<name>.feature`
— one file per macro or model, feature files discovered recursively.

`--engine fake` (the default) skips dbt entirely: each `.feature` file may
have a co-located `.canned.py` exposing `CANNED_RESULTS`, useful for
testing specdbt itself or prototyping a scenario's shape before wiring up
a real model.

## Writing scenarios

See `docs/knowledge/gherkin-style-guide.md` for the full style guide. The short
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

## Documentation

Architecture reference lives in [`docs/knowledge/`](docs/knowledge/index.md)
— a knowledge bundle in [Open Knowledge
Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
v0.2 (Google's OKF spec): one concept doc per module/decision, frontmatter
+ cross-links. Start at `docs/knowledge/index.md`. Claude Code users get
it loaded on demand via the `/specdbt` skill instead of re-reading
`src/specdbt/` from scratch.

## Development

Fast path, needs [`just`](https://github.com/casey/just#installation):
```bash
just setup   # uv sync + pre-commit install, checks uv is installed first
just test    # test suite
```
`just doctor` checks for required/optional tools (`uv`, Docker) and
prints an install command for anything missing. `just` alone lists all
targets.

Manual path:
```bash
uv sync                    # once, pulls in pre-commit
uv run pre-commit install  # once, wires the git hook
uv run pytest               # test suite
uv run pre-commit run --all-files   # everything the hook checks, on demand
```

`.pre-commit-config.yaml` runs `ruff` (lint + format), `ty` (type
checking), `uv-lock` (lockfile/pyproject drift), `typos`,
`validate-pyproject`, `gitleaks` (staged-diff secret scan), and a
handful of hygiene checks (trailing whitespace, merge conflict markers,
etc.) on every commit. CI runs the identical `pre-commit run
--all-files` — same checks, same config, in case a commit skipped the
local hook (`--no-verify` or a first-time clone without `pre-commit
install`). The one exception is secret scanning: the pre-commit
`gitleaks` hook only sees a commit's staged diff, which is always empty
against a clean CI checkout, so CI runs a separate `gitleaks-action`
job that scans the repository's full history instead.

The test suite includes an end-to-end test that runs the real example
project through the real CLI (`tests/test_examples_jaffle_shop.py`) — a
green suite means the examples above actually work, not just that unit
tests pass.

### Testing against other adapters

The default `uv run pytest` above only exercises DuckDB. The macro tier's
adapter-dispatch code routes schema DDL, fixture CTAS, and ref/source
substitution through dbt-core's own adapter-dispatch primitives so the
same scenarios run unmodified against other engines. It has two more
adapter-specific test files, both skipped unless you opt in — neither is
required for the default suite to pass.

**Postgres** (runnable locally, and CI-verified):

Fast path, needs [`just`](https://github.com/casey/just#installation) and
Docker:
```bash
just postgres-up     # starts Postgres in Docker, writes .env if missing
just test-postgres   # exports the right env vars, runs the test
```
`just doctor` checks for `uv`/Docker and prints an install command for
whichever is missing.

Manual path, if you'd rather not install `just`:
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
default): see `docs/knowledge/databricks-validation-checklist.md`.

## Limitations, by design

- `specdbt run` executes whatever's in a `.feature` file's `.canned.py`
  companion (`--engine fake`) or compiles and runs real dbt SQL
  (`--engine dbt`) — don't run it against scenarios you haven't reviewed,
  the same way you wouldn't run an unreviewed `conftest.py`.
- The step-by-step summary counts only steps that were actually
  attempted — a scenario that fails partway through under-reports its
  remaining steps as "not there" rather than explicitly "skipped."

## Contributing

Issues, ideas, and PRs are welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md)
for local setup, conventions, and the release process. The
`ExecutionAdapter` interface (`src/specdbt/adapters/base.py`) is the
extension point for a new backend (a different warehouse, a different
execution engine) — one new class, not a rewrite.

## License

MIT — see `LICENSE`.
