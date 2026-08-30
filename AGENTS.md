# specdbt — Agent Notes

This repo's architecture is documented as an OKF knowledge bundle in
[`docs/knowledge/`](docs/knowledge/index.md) — start there before reading
`src/specdbt/` from scratch to answer a design question.

## Conventions

- Tests mirror `src/` 1:1 under `tests/` (e.g. `src/specdbt/runner.py` ->
  `tests/specdbt/test_runner.py`).
- Gherkin scenario style: see [`docs/gherkin-style-guide.md`](docs/gherkin-style-guide.md).
- Databricks-specific test considerations: see
  [`docs/databricks-validation-checklist.md`](docs/databricks-validation-checklist.md).
