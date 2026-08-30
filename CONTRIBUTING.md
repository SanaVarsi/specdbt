# Contributing to specdbt

Issues, ideas, and PRs are welcome.

## Before you start

[`docs/knowledge/index.md`](docs/knowledge/index.md) is the source of
truth for this repo's architecture and conventions — read it (or have
your agent load it via the `/specdbt` skill) before making non-trivial
changes. `AGENTS.md` covers test-file layout and links the
[Gherkin style guide](docs/knowledge/gherkin-style-guide.md) for writing
`.feature` scenarios.

The `ExecutionAdapter` interface (`src/specdbt/adapters/base.py`) is the
extension point for a new backend — one new class, not a rewrite.

## Local setup

```bash
just setup   # uv sync + pre-commit install (see `just doctor` if uv/Docker is missing)
just test    # full test suite
```
Without `just`: `uv sync && uv run pre-commit install && uv run pytest`.

Pre-commit runs ruff, ty, uv-lock, typos, gitleaks, and hygiene checks on
every commit; CI runs the identical set (`pre-commit run --all-files`).
Exception: `gitleaks` pre-commit only scans the staged diff, so CI also
runs a separate `gitleaks-action` job over full history.

`uv run pytest` alone only exercises DuckDB. Two more test files cover
other adapters, both skipped unless you opt in:

**Postgres** (CI-verified, runnable locally with Docker):
```bash
just postgres-up     # starts Postgres in Docker, writes .env if missing
just test-postgres   # exports the right env vars, runs the test
```
Manual path: create a gitignored `.env` with `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `POSTGRES_DB`; `docker compose up -d postgres`; then
export those same values as `SPECDBT_PG_USER`/`SPECDBT_PG_SECRET`/
`SPECDBT_PG_DBNAME` plus `SPECDBT_PG_HOST=localhost SPECDBT_PG_PORT=5432
SPECDBT_TEST_POSTGRES=1` and run `uv run pytest
tests/test_dbt_adapter_postgres.py -v` (see `tests/conftest.py` for why
the names differ).

**Databricks** (manual, needs your own workspace, no CI): see
`docs/knowledge/databricks-validation-checklist.md`.

## Pull requests

- Keep tests mirroring `src/specdbt/` under `tests/` (see `AGENTS.md`).
- `uv run pre-commit run --all-files` and `uv run pytest` clean before
  pushing.
- Describe the behavior change, not just the diff — a scenario or test
  demonstrating it is the strongest review evidence.

## Release process (maintainers)

Versioning is manual. Bump `version` in `pyproject.toml`, then tag and
publish a GitHub Release from that commit. The tag must be `vX.Y.Z`,
matching the `pyproject.toml` value exactly.

The release workflow then runs on publish: full CI suite against that
tag, build, and a PyPI publish step using trusted publishing, so there is
no stored API token.

One-time repo setup this depends on, all separate from anything in this
repo's code:
- a PyPI trusted publisher entry pointing at this repo
- a GitHub environment named `pypi`
- a repo secret the CI Postgres job reads (see `ci.yml`)
