# specdbt — Agent Notes

For any question about this repo's design, conventions, or testing
approach, consult the OKF knowledge bundle at
[`docs/knowledge/`](docs/knowledge/index.md) first — it is the source of
truth for this repo's architecture and conventions. Only fall back to
reading `src/specdbt/` from scratch when the bundle doesn't cover what
you need.

## Conventions

- Tests mirror `src/specdbt/` under `tests/`, with the package level
  flattened (e.g. `src/specdbt/runner.py` -> `tests/test_runner.py`,
  `src/specdbt/dbt_integration/fixture_sql.py` ->
  `tests/dbt_integration/test_fixture_sql.py`) — not always 1:1; some
  source files share a test file or split across several.
- Gherkin scenario style: see
  [`docs/knowledge/gherkin-style-guide.md`](docs/knowledge/gherkin-style-guide.md).
- Databricks-specific test considerations: see
  [`docs/knowledge/databricks-validation-checklist.md`](docs/knowledge/databricks-validation-checklist.md).
