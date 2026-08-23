# specdbt — Phase 0 Design (Skeleton Pipeline)

**Status:** approved 2026-08-23. Source material: `~/dev/cv/dbtspec-plan/00`–`05` (the original planning docs, working name `dbtspec`, renamed here — see §1).

## 1. What and why

BDD (`Given`/`When`/`Then`) testing layer for dbt models. Full rationale, problem statement, and prior-art check live in the original plan docs (`00-overview-and-vision.md`); not repeated here. This spec covers only **Phase 0**: the skeleton that proves the parser → fixture → adapter → assertion → report pipeline end-to-end, per `04-roadmap-and-phases.md`.

**Name:** `specdbt` (renamed from the working name `dbtspec`). Verified 2026-08-23: unregistered on PyPI, no exact-match GitHub repository.

## 2. Scope of this phase

In scope:
- Gherkin `.feature` parsing to an AST.
- Fixture Builder: data-table steps → typed in-memory fixture objects.
- `ExecutionAdapter` ABC (the engine-agnostic interface from `02-technical-design.md` §2.3) plus one concrete adapter: `FakeAdapter`, which returns hardcoded/pre-programmed rows — no real SQL or Polars execution yet.
- Assertion Engine: row-count, not-null, unique, accepted-values `Then` steps.
- Reporter: terminal output in Gherkin's own language (pass/fail per step).
- CLI: `specdbt init` (scaffold a `features/` dir) and `specdbt run features/` (parse + execute via `FakeAdapter` + report).
- 3–5 hand-written `.feature` files against **real** data-pulse models (§5) — chosen specifically to exercise the assertion vocabulary before any real engine exists.

Explicitly out of scope for this phase (later phases per the roadmap doc):
- `PolarsAdapter`, `DuckDBAdapter`, `DbtCoreAdapter`, `--parity` mode — Phase 1.
- `compile --to dbt-unit-tests` — Phase 2.
- Any AI feature (`generate`, fixture synthesis, failure triage) — Phase 3. The `ai/` package is scaffolded with typed stubs (`NotImplementedError`) so the Phase 1+ repo shape matches `02-technical-design.md` §3 from day one, but nothing in it executes.
- CI wiring — needs a remote to push to; this repo stays local-only for now per explicit instruction.

## 3. Repo

Local git repo at `~/dev/specdbt`, independent of `data-pulse` and `cv` (no submodule/path coupling — Phase 0's `FakeAdapter` needs realistic model/column *names*, not the other repo's files at runtime).

```
specdbt/
├── src/specdbt/
│   ├── __init__.py
│   ├── parser.py              # Gherkin -> AST (gherkin-official)
│   ├── fixtures.py            # Fixture Builder
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py            # ExecutionAdapter ABC, Fixture, ExecutionResult
│   │   └── fake_adapter.py    # Phase 0's only concrete adapter
│   ├── assertions.py           # Then-step library
│   ├── reporter.py
│   ├── ai/
│   │   ├── __init__.py
│   │   └── stubs.py            # NotImplementedError placeholders, typed interface only
│   ├── cli.py
│   └── py.typed
├── tests/                       # pytest, mirrors src/ layout
├── examples/
│   └── data_pulse/
│       └── features/            # the real-model .feature files, see §5
├── docs/superpowers/{specs,plans}/
├── pyproject.toml               # uv-managed
├── .gitignore
├── LICENSE                      # MIT
└── README.md
```

## 4. Component contracts (Phase 0)

Exact `ExecutionAdapter` ABC and `Fixture`/`ExecutionResult` dataclasses as specified in `02-technical-design.md` §2.3 — reused verbatim, not redesigned here.

`FakeAdapter.run_model(model_name, fixtures)`:
- Constructed with a registry: `dict[str, ExecutionResult]` mapping `model_name` → a **hardcoded** canned result. `run_model` just looks up and returns it — it never inspects `fixtures` or computes anything. This is deliberate, per `04-roadmap-and-phases.md` Phase 0 ("a fake in-memory adapter that just returns hardcoded rows"): Phase 0 proves the parser→fixture→adapter→assertion→report *plumbing*, not model correctness. Real transform logic — and the actual correctness guarantee — is `PolarsAdapter`/`DuckDBAdapter`'s job in Phase 1.
- For specdbt's own unit tests: the canned result is set up inline in the test.
- For the real-model `.feature` files (§5): a small companion module, `examples/data_pulse/features/canned_results.py`, hand-codes the manually-verified expected output per scenario (e.g., for `silver_weather`, a human works out by hand which input rows survive the `WHERE timestamp IS NOT NULL` filter and hardcodes that result). This makes explicit, in code, that these scenarios are not yet a correctness check — that arrives in Phase 1.

Assertion vocabulary for Phase 0 (subset of `02-technical-design.md` §2.5, the four with the clearest, most mechanical evaluation against any row list):
```gherkin
Then "<model>" should have <N> row(s)
Then column "<col>" in "<model>" should not contain nulls
Then column "<col>" in "<model>" should be unique
Then the row for <key_col> "<key_val>" should have <col> <value>
```

Reporter: terminal only for Phase 0 (echo scenario text + ✓/✗ per step, summary line). JUnit XML output deferred to Phase 1 (it matters once this runs in CI; Phase 0 has no CI).

## 5. Real target models (data-pulse)

Pulled from `~/dev/data-pulse/transforms/models/` on 2026-08-23. Feature files target these by name/shape only — no filesystem or runtime dependency on the data-pulse repo.

| Model | Shape | Why it's useful for Phase 0 |
|---|---|---|
| `silver_weather` | Cast/rename columns from `bronze_weather`, `WHERE timestamp IS NOT NULL` | Simplest case: row-exclusion behavior, one assertion per column type. |
| `gold_weather_daily` | `GROUP BY date` aggregation (avg/max/min/sum/count) | Row-count-changes-with-grouping case. |
| `gold_weather_anomalies` | Window function (rolling avg/stddev) + two `CASE WHEN` branches (`z_score`, `is_anomaly`) | Real multi-branch conditional logic — exactly the "untested CASE branch" problem named in `00-overview-and-vision.md` §1.3. Two scenarios: inside vs. outside the anomaly threshold. |

5 scenarios planned across these three models (2 for anomalies' branches, 1–2 each for the other two) — within the plan's "3–5" target.

## 6. Tooling & dependency security

- `uv` for env/deps (project already has it; system Python is 3.9.6, too old — `uv` provisions its own). Target `>=3.12`.
- `ruff` for lint + format, `pytest` for specdbt's own test suite (TDD: red/green per component, per the repo's standing workflow preference).
- License: MIT.
- **Before adding any new dependency**: check PyPI metadata (maintainer, release cadence, download count — reject anything that looks abandoned or typosquat-shaped) and run a vuln lookup (`pip-audit` against the resolved lock, or an OSV API check) before it's added to `pyproject.toml`. Reported to the user, not silently done. Expected Phase 0 dependency set is small and all well-established: `gherkin-official`, `click` or `typer` (CLI), `pytest`/`ruff` (dev-only).

## 7. Commit plan (local only, no push)

1. Scaffold: `pyproject.toml`, `.gitignore`, `LICENSE` (MIT), directory skeleton, this spec doc under `docs/superpowers/specs/`.
2. Gherkin parser wrapper + fixture builder, with tests.
3. `ExecutionAdapter` ABC + `FakeAdapter`, with tests.
4. Assertion engine + reporter, with tests.
5. CLI (`init`, `run`) wiring the pipeline together, with tests.
6. Real `.feature` files against the three data-pulse models (§5) + README describing the project and how to run it.

Each commit lands only after its own tests pass (TDD), per `superpowers:test-driven-development`.

## 8. Definition of done (Phase 0)

Matches `04-roadmap-and-phases.md` Phase 0 deliverable exactly: `specdbt run examples/data_pulse/features/` parses the real `.feature` files, executes them through `FakeAdapter`, and prints a readable pass/fail report — end-to-end, no stubbed-out step. Phase 1 (real `PolarsAdapter`/`DuckDBAdapter`, `--parity`) is the next spec, not part of this one.
