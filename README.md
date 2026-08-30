# specdbt

BDD-style `Given`/`When`/`Then` testing for dbt models. Write scenarios a
stakeholder can read, get a fast structural check today and a real-SQL
correctness guarantee once Phase 1 lands.

**Status: Phase 0** — the parser → fixture → adapter → assertion → report
pipeline works end to end against a `FakeAdapter` (hardcoded rows, no real
SQL/Polars execution yet). See `docs/superpowers/specs/2026-08-23-specdbt-phase0-design.md`
for what's in and out of scope, and `docs/superpowers/plans/2026-08-23-specdbt-phase0.md`
for how it was built.

## Quickstart

```bash
uv sync
uv run specdbt init features/       # scaffold an example .feature + its canned result
uv run specdbt run features/        # parse, run, report
```

## How a scenario looks

```gherkin
Feature: Silver weather standardization — null timestamp handling

  Scenario: A row with a null timestamp is dropped
    Given the following rows in "bronze_weather":
      | timestamp           | temperature | ... |
      | 2026-08-18 06:00:00 | 18.2        | ... |
      | NULL                | 19.0        | ... |
    When the "silver_weather" model runs
    Then "silver_weather" should have 1 row
```

`NULL` is the explicit null literal in a Gherkin table cell — a blank cell
means an empty string, not null; the two are never conflated.

Each `.feature` file may have a co-located `.canned.py` file exposing
`CANNED_RESULTS: dict[str, ExecutionResult]` — Phase 0's `FakeAdapter` returns
these hardcoded rows rather than computing anything, to prove the pipeline
plumbing before a real execution engine exists (Phase 1: `PolarsAdapter` /
`DuckDBAdapter`).

## Development

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

## Roadmap

Phase 0 (this): skeleton pipeline, `FakeAdapter`, CLI, dogfooded on real models.
Phase 1: real `PolarsAdapter`/`DuckDBAdapter`, `--parity` mode. Phase 2: compile
scenarios to native dbt `unit_tests:` YAML. Phase 3: AI-assisted fixture
synthesis, NL→Gherkin, failure triage (stubs already scaffolded in `src/specdbt/ai/`).

## Testing against other adapters

The default `uv run pytest` above only exercises DuckDB. The macro tier's
adapter-dispatch code routes schema DDL, fixture CTAS, and ref/source
substitution through dbt-core's own adapter-dispatch primitives so the
same scenarios run unmodified against other engines. It has two more
adapter-specific test files, both skipped unless you opt in — neither is
required for the default suite to pass.

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

This is an early-stage, unclaimed niche (no existing BDD layer for dbt) built
in the open with community use in mind — issues, ideas, and PRs are welcome
once this reaches a public repository. The `ExecutionAdapter` interface
(`src/specdbt/adapters/base.py`) is the extension point: a new backend (a
different warehouse, a different execution engine) is one new class, not a
rewrite.

**Known Phase 0 limitations** (by design, not oversight — Phase 1 removes
most of them):
- The 5 example scenarios prove the pipeline plumbing end to end; they don't
  independently validate the real dbt models' logic (`FakeAdapter` returns
  hand-authored canned rows, it doesn't compute anything). That correctness
  guarantee is what Phase 1's real adapters + `--parity` mode add.
- `FakeAdapter` maps one model name to one canned result, so two scenarios
  against the same real model currently need separate `.feature` files —
  which is why the report can print the same `Feature:` name more than once
  if two files happen to share a title. Distinct titles per file avoid this
  for now; Phase 1's real adapters (which compute from fixtures instead of a
  static lookup) remove the constraint.
- `specdbt run` executes whatever Python is in a `.feature` file's
  `.canned.py` companion — don't run `specdbt run` against `.feature`/
  `.canned.py` pairs you haven't reviewed, the same way you wouldn't run an
  unreviewed `conftest.py`.
- The step-by-step summary counts only steps that were actually attempted —
  a scenario that fails partway through under-reports its remaining steps as
  "not there" rather than explicitly "skipped."

## License

MIT — see `LICENSE`.
