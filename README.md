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

## Try it against real models

`examples/data_pulse/features/` has 5 scenarios written against real models
from a live dbt project, including both branches of a `CASE WHEN` in an
anomaly-detection model:

```bash
uv run specdbt run examples/data_pulse/features
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
uv run pytest       # test suite
uv run ruff check .
uv run ruff format .
```

## Roadmap

Phase 0 (this): skeleton pipeline, `FakeAdapter`, CLI, dogfooded on real models.
Phase 1: real `PolarsAdapter`/`DuckDBAdapter`, `--parity` mode. Phase 2: compile
scenarios to native dbt `unit_tests:` YAML. Phase 3: AI-assisted fixture
synthesis, NL→Gherkin, failure triage (stubs already scaffolded in `src/specdbt/ai/`).

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
