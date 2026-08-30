# specdbt — Agent Notes

This repo's architecture is documented as an OKF knowledge bundle in
[`docs/knowledge/`](docs/knowledge/index.md) — start there before reading
`src/specdbt/` from scratch to answer a design question.

## Conventions

- Tests mirror `src/specdbt/` under `tests/`, with the package level
  flattened (e.g. `src/specdbt/runner.py` -> `tests/test_runner.py`,
  `src/specdbt/dbt_integration/fixture_sql.py` ->
  `tests/dbt_integration/test_fixture_sql.py`) — not always 1:1; some
  source files share a test file or split across several.
- Gherkin scenario style: see [`docs/gherkin-style-guide.md`](docs/gherkin-style-guide.md).
- Databricks-specific test considerations: see
  [`docs/databricks-validation-checklist.md`](docs/databricks-validation-checklist.md).
