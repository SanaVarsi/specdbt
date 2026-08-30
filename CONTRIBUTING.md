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
every commit; CI runs the identical set. See the README's Development
section for running the Postgres/Databricks adapter tests.

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
