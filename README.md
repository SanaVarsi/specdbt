# specdbt

[![CI](https://github.com/SanaVarsi/specdbt/actions/workflows/ci.yml/badge.svg)](https://github.com/SanaVarsi/specdbt/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](pyproject.toml)

BDD-style `Given`/`When`/`Then` testing for dbt models and macros. Write a
scenario a stakeholder can read; specdbt compiles and runs it for real
against dbt and reports pass/fail — no hand-maintained YAML, no
hardcoded expected output.

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

Models compile to a real dbt `unit_tests:` entry and run via `dbt test`.
Macros — which dbt [has no native way to unit test][dbt-10547] — run
through a real ephemeral-table/`dbt show` pipeline instead. Any warehouse
dbt-core supports is in scope; DuckDB and Postgres are CI-verified,
Databricks is manually validated (see [docs](docs/knowledge/index.md)).

[dbt-10547]: https://github.com/dbt-labs/dbt-core/issues/10547

## Install

```bash
uv add --dev specdbt          # or: pip install specdbt
```

Add your warehouse's dbt adapter alongside it, e.g. `uv add --dev
"specdbt[postgres]"` (`databricks`, `snowflake` extras also available;
DuckDB ships built in).

## Quickstart

```bash
uv add --dev specdbt
uv run specdbt init features/                 # scaffold an example .feature file
uv run specdbt run features/ \
  --engine dbt --project-dir . --target <your target>
```

## Docs

- [`docs/knowledge/index.md`](docs/knowledge/index.md) — architecture,
  adapters, the two-tier model/macro design.
- [`docs/knowledge/gherkin-style-guide.md`](docs/knowledge/gherkin-style-guide.md)
  — how to write scenarios.
- [`examples/jaffle_shop/`](examples/jaffle_shop) — a full worked example
  (`just run-example`).
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — local setup, testing other
  adapters, release process.

## License

MIT — see [`LICENSE`](LICENSE).
