# specdbt — Phase 1 Design (DRAFT — awaiting review, not started)

**Status: proposal only.** Written 2026-08-23 immediately after Phase 0 shipped
(see `2026-08-23-specdbt-phase0-design.md` and its plan doc). Nothing in this
document has been implemented, and no new dependency has been added or
installed — Phase 0's own rule (check before installing, report what was
checked) plus the fact that new dependencies and backend choices are a
decision for you to see before they land, not one to make while you're away.
Treat this as the equivalent of the Phase 0 brainstorm-and-design step,
minus the live Q&A — read it, tell me what to change, and I'll fold that in
before turning it into an implementation plan the same way Phase 0 got one.

## 1. Goal

Replace Phase 0's `FakeAdapter` (hardcoded rows, no computation) with two real
adapters that actually run model logic, per `04-roadmap-and-phases.md` Phase 1
and `01-architecture-options-pros-cons.md`'s Option A recommendation:

- `PolarsAdapter` — reimplements a model's transform as a `polars` expression
  pipeline, run against the scenario's own `Given` fixtures. Fast, in-memory,
  the sub-second default.
- `DuckDBAdapter` — materializes fixtures as real DuckDB temp tables and runs
  the model's *actual* compiled SQL against them. Slower, but it's the real
  engine, not a reimplementation.
- `--parity` mode — runs a scenario through both and diffs the results. This
  is the direct answer to Phase 0's known correctness gap (`FakeAdapter`
  proves plumbing, not model correctness) and to the architectural risk named
  explicitly in the architecture doc: a Python reimplementation can drift from
  the real SQL, and parity mode turns that into an automated check instead of
  a hope.

This also removes Phase 0's one-canned-result-per-model-name limitation
(documented in the current README) since both real adapters compute from
whatever fixtures a scenario provides, instead of a static lookup — multiple
scenarios can share one real model name again, the normal Gherkin shape.

## 2. Scope

**In scope:**
- `PolarsAdapter` reimplementing 2–3 of data-pulse's actual models. Proposed,
  in order of complexity: `silver_weather` (filter + casts — the simplest),
  `gold_weather_daily` (group-by aggregation), `gold_weather_anomalies`
  (window functions + `CASE WHEN` — the one that most needs a real engine,
  since Phase 0's canned rows for it were hand-computed, not verified).
- `DuckDBAdapter` running the *actual* SQL from `~/dev/data-pulse/transforms/
  models/**/*.sql` (read-only reference to that repo's files at test-run time
  — still no runtime coupling beyond reading the `.sql` text, consistent with
  Phase 0's "no filesystem dependency on data-pulse" principle applied to the
  *fixture format*, not to this new adapter's actual job of running real SQL).
- `--parity` CLI flag and the diff/report format for a parity mismatch.
- Migrating the 5 existing example scenarios off `.canned.py` files onto the
  real adapters — this is also how Phase 1 validates that the Phase 0
  hand-computed canned values were actually correct (the advisor review that
  caught the Phase 0 null/blank-cell bug flagged that the Phase 0 test suite
  never independently checked that arithmetic; Phase 1 is what actually
  checks it).

**Out of scope (later phases, unchanged from the original roadmap):**
- `DbtCoreAdapter` (shells out to `dbt test`) — Phase 2.
- `compile --to dbt-unit-tests` — Phase 2.
- Any AI feature — Phase 3.
- Multi-warehouse support — not planned; DuckDB-first per the original vision
  doc's non-goals.

## 3. New dependencies (NOT yet checked or installed)

- `polars` — the Rust-backed DataFrame library the whole "Option A" bet rests
  on (see architecture doc §A).
- `duckdb` — Python bindings for DuckDB, to materialize fixtures as temp
  tables and run real compiled SQL against them.

Both need the same security check Phase 0 used before either is added to
`pyproject.toml`: PyPI metadata sanity (maintainer, release cadence, download
count) and an OSV.dev / `pip-audit` vulnerability lookup, reported before
installing, not after. Both are extremely widely used, so I'd expect this to
pass cleanly, but it hasn't been run yet and I'm not running it until this
spec is approved — installing dependencies is exactly the kind of
outward/hard-to-fully-reverse action that should wait for a live green light
rather than happen while you're offline.

## 4. Open questions for you (this is why this is a draft, not a plan)

1. **`PolarsAdapter` model selection** — the 3 proposed above, or a different
   subset? `gold_weather_anomalies`'s window functions are the most
   interesting Polars work but also the most complex to get right.
2. **DuckDB read of data-pulse's actual `.sql` files at test time** — fine as
   proposed (read-only, no write access, no dependency beyond reading text),
   or would you rather vendor copies of the specific model SQL into
   `examples/data_pulse/` so this repo has zero filesystem reference to
   `~/dev/data-pulse` at all, ever? Trade-off: read-only reference stays
   trivially in sync with the real project; vendored copies drift silently if
   the real models change but are fully self-contained.
3. **Parity-mismatch UX** — what should `--parity` print on a mismatch? A
   proposal: same report format as today, but a mismatched scenario gets a
   third line per differing field (`Polars: X, DuckDB: Y`) instead of a single
   pass/fail mark, so a parity failure reads differently from a logic failure
   at a glance.
4. **Timeline** — Phase 1 is scoped at 2–3 weeks in the original roadmap doc.
   Given you're job-searching in parallel, do you want this paced the same
   way (nights/weekends, not blocking applications), or is there a reason to
   move faster/slower than that now?

## 5. What doesn't change

Everything above the `ExecutionAdapter` line (spec: Phase 0 doc §1 diagram) —
Gherkin parser, Fixture Builder, assertion engine, reporter, CLI shape. This
is the property Phase 0 was built to prove holds, and Phase 1 is the first
real test of that claim: `PolarsAdapter`/`DuckDBAdapter` are new classes
implementing the same `run_model(model_name, fixtures) -> ExecutionResult`
contract Phase 0 already shipped and tested. If either needs to change that
interface, that's a signal the Phase 0 abstraction has a gap worth naming
before writing more code against it.
