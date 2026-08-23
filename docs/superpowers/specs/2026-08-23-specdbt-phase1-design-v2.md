# specdbt — Phase 1 Design v2 (replaces the Polars/DuckDB-reimplementation draft)

**Status: approved design, not yet an implementation plan.** Supersedes
`2026-08-23-specdbt-phase1-design.md` (kept for history, marked superseded).
This doc reflects a real architecture change made during review, not a
refinement of the old one — see §1.

## 1. Why this replaces v1

The original Phase 1 draft proposed reimplementing model logic in Polars and
DuckDB, with a `--parity` mode diffing the two reimplementations against each
other. Review surfaced three problems with that bet:

1. **It can't test macros at all.** A macro is a Jinja template, not a shape
   Polars can reimplement. The user's actual need — testing macros, which dbt
   itself has no native unit-test support for (open feature request,
   [dbt-core#10547](https://github.com/dbt-labs/dbt-core/issues/10547), filed
   Aug 2024, "Refinement needed," no maintainer commitment on shape or
   timeline) — was structurally out of reach for v1's design.
2. **It reintroduces exactly the drift risk Phase 0's own README flagged.**
   Two hand-maintained reimplementations of real SQL logic can each silently
   diverge from the truth; `--parity` mode only proves they agree with each
   other, not that either is correct.
3. **It doesn't generalize to Snowflake/Databricks.** A Polars reimplementation
   is one specific engine's semantics; real dbt projects run on whatever
   warehouse the team uses, and dialect differences (window functions, date
   arithmetic, type coercion) are exactly what a reimplementation would get
   subtly wrong per-warehouse.

v2's bet instead: **specdbt writes no execution logic of its own for models or
macros — it drives real dbt (`dbtRunner`, the same programmatic entrypoint dbt
Cloud/CLI use) against whatever adapter the project already targets, and adds
only a Gherkin front end and a Polars-based result comparison on top.**
Adapter-agnosticism is inherited from dbt's own adapter system, not rebuilt
inside specdbt.

## 2. Scope

**In scope:**
- `DbtExecutionAdapter` — real execution via `dbtRunner`, one implementation
  for all engines (see §3).
- Model testing via dbt's native `unit_tests:` YAML (§4), including
  incremental-model scenarios via `is_incremental` overrides and `input: this`.
- Macro testing via specdbt's own ephemeral-schema mechanism (§5) — the only
  option today, since dbt has no native equivalent (dbt-core#10547).
- Gherkin grammar additions for macro invocation and tier/adapter tags (§6).
- A style guide mandating declarative Gherkin, and a `specdbt docs` living-
  documentation command (§7).
- Example scenarios against jaffle_shop (models) and dbt_utils (macros),
  replacing the data-pulse examples (§8).
- Safety guardrails for a tool that now touches real (ephemeral) warehouse
  schemas, not just in-memory fakes (§9).

**Out of scope for Phase 1 (extension points only, not implemented):**
- Model testing via the integration tier (real ephemeral-schema deploy for
  models, not just macros) — architecturally supported by the same
  `DbtExecutionAdapter.run_model`, just not exercised by any Phase 1 example.
- Macro testing via a unit tier — no native dbt mechanism exists yet; see §5.4
  for the registered-but-empty extension point.
- Live Snowflake/Databricks validation — architecturally engine-agnostic by
  construction (nothing DuckDB-specific in specdbt's own code), but unproven
  against a real account. No credentials available to test with.
- Any AI feature (fixture synthesis, NL→Gherkin, edge-case advisor) — still
  Phase 3, per the original roadmap. §7's `@ai-generated` tag is a hook for
  that phase, not an implementation of it.

## 3. Architecture: one real adapter, two test tiers

`ExecutionAdapter` (Phase 0, `src/specdbt/adapters/base.py`) stays as the
interface for real engine execution, extended (see §10 for the exact diff).
`FakeAdapter` stays too, demoted to "what specdbt uses to test itself" — its
own test suite shouldn't need a live dbt project to run.

Phase 1 adds exactly one concrete real adapter, `DbtExecutionAdapter`, driving
`dbtRunner.invoke([...])`. This is deliberately the same CLI-shaped entrypoint
dbt Cloud and the dbt CLI use — confirmed via dbt Labs' own Fusion-engine posts
that Fusion is being built as a CLI-compatible drop-in (`dbt --version` etc.),
so building on this surface rather than internal manifest APIs is the
forward-compatible choice, not just the convenient one.

**Test tier is orthogonal to resource kind** (model vs. macro) — this was the
key correction from the first pass of this design, which had wrongly tied
"model = unit-tested" and "macro = integration-tested" together:

| | Unit tier (delegates to dbt-native fixtures) | Integration tier (specdbt's own ephemeral-schema execution) |
|---|---|---|
| **Model** | ✅ `unit_tests:` YAML + `dbt test` — Phase 1 proves this | Extension point only — same mechanism as macros, not exercised in Phase 1 |
| **Macro** | Extension point only — no native dbt mechanism exists (dbt-core#10547 open) | ✅ ephemeral schema + real run — Phase 1 proves this, and it's not a stopgap: see §5.5 |

Two tiers, two orchestration interfaces:

- **`ExecutionAdapter`** (real engine execution — integration tier). Extended
  in Phase 1 with `run_macro(macro_call, fixtures) -> ExecutionResult`
  alongside the existing `run_model(model_name, fixtures) -> ExecutionResult`.
- **`NativeTestCompiler`** (new, unit tier — delegates to whatever native
  fixture mechanism dbt ships for a given resource kind). A registry keyed by
  resource kind: `ModelUnitTestCompiler` registered in Phase 1; a macro slot
  left unregistered, raising a clear "not supported by dbt yet — see
  dbt-core#10547, use `@integration`" error if a scenario asks for it.

The runner (`src/specdbt/runner.py`) picks tier per scenario: explicit
`@unit`/`@integration` tag if present, else "unit if a compiler is registered
for this resource kind, else integration."

## 4. Model path: unit tier (dbt-native)

specdbt compiles each tagged-`@unit` model `Scenario` into a `unit_tests:`
YAML entry and runs it via `dbtRunner.invoke(["test", "--select",
f"unit_test:{project}.{name}"])`, translating dbt's own pass/fail and
actual-vs-expected diff into specdbt's existing report format
(`src/specdbt/reporter.py`). No ref/source-override logic of specdbt's own —
dbt's unit test runner already does this correctly, per-adapter, and specdbt
reusing it means Snowflake/Databricks support requires zero specdbt code, only
dbt itself supporting the adapter (which it already does).

**Incremental models are in scope**, not a punt — dbt's own `unit_tests:`
config supports this directly via `overrides: macros: is_incremental:
true/false` and a special `input: this` fixture representing "rows already in
the target table." specdbt's Gherkin shape for this: a
`Given the following rows already in "<model>"` step compiles to `input:
this`; which `is_incremental` branch a scenario exercises is either explicit
(a tag or step wording) or, if the model has an incremental config, specdbt
generates both branches from one scenario by default — exact step grammar is
an implementation-plan-time detail, not a design blocker.

**Accurate non-goals, inherited from dbt itself, not invented by specdbt:**
per dbt's own unit-test prerequisites, this path doesn't support Python
models, `materialized view` models, recursive SQL, or models outside the
current project, and doesn't support introspective queries. These aren't
specdbt limitations to work around — routing around them would mean
reimplementing the exact machinery this design deliberately avoids
reimplementing. A scenario hitting one of these gets a clear "dbt's native
unit tests don't support this — use `@integration`" error, since the
integration-tier extension point (§2) can, in principle, still test it.

## 5. Macro path: integration tier (specdbt-native, real execution)

This is Phase 1's other proven cell, and the direct answer to "test macros
end-to-end against dbt's real execution."

### 5.1 Mechanism

One ephemeral schema per scenario run, named `specdbt_<uuid>`, created and
torn down entirely through `dbtRunner.invoke(["run-operation", "--sql", ...])`
— the same officially documented mechanism dbt itself uses for ad-hoc
DDL/DML against the real target connection:

1. **Given → real tables.** Each fixture is materialized via a `CREATE TABLE
   ... AS` with a literal `VALUES` list, built using dbt's own cross-database
   type/literal macros (`dbt.type_string`, `dbt.string_literal`, etc. — the
   same macros `dbt_utils` itself uses internally for cross-adapter
   compatibility) so literal formatting is correct per-warehouse without
   specdbt hand-writing dialect SQL.
2. **When → real macro call.** The macro call is real, verbatim Jinja — no
   specdbt-invented call syntax to keep in sync with dbt's own (see §6) —
   wrapped in a `CREATE TABLE ... AS (<macro call>)` and executed the same
   way. Any `ref()`/`source()` inside that literal referring to a fixture name
   is substituted for the ephemeral fixture's real relation before execution.
3. **Result readback.** The result table is read back via `dbt show --inline`
   into a Polars DataFrame.
4. **Then → Polars diff** against the expected rows, using the same
   assertion vocabulary Phase 0 already built (`src/specdbt/assertions.py`).
5. **Teardown.** Schema dropped in a `finally` — runs whether the scenario
   passed, failed, or raised, not conditional on success.

*(Two implementation details — the exact `dbtRunner` result object shape for
capturing pass/fail programmatically, and the exact `dbt show --inline`
result-capture API — need verifying against the installed dbt-core version at
plan-writing time; noted here rather than asserted, since I haven't run this
code yet.)*

### 5.2 Because fixtures are real tables, introspective macros are in scope

Unlike the model/unit-tier path, there's no inherited dbt limitation here —
`star()`, `run_query()`, anything needing to introspect a real relation works,
because the fixture *is* a real relation by the time the macro runs, and the
connection is live throughout. (An earlier pass of this design wrongly listed
introspective macros as a non-goal, carrying over reasoning from the
compile-only approach this doc replaced — corrected here.)

### 5.3 Safety guardrails

Real, possibly-shared warehouse connections change the risk profile from
Phase 0's in-memory `FakeAdapter`:
- Every specdbt-created object lives under `specdbt_<uuid>` — never the
  project's real schemas.
- Teardown always runs, including on interrupt where feasible (best-effort,
  documented as such — not guaranteed if the process is hard-killed).
- `--keep-schema` debug flag skips teardown so a failure can be inspected by
  hand.
- A heuristic guard refuses to run against a target whose configured schema
  doesn't look like dev/test, with an explicit `--i-know-what-im-doing`
  override — a blunt check against accidentally pointing this at prod.

### 5.4 Forward-compat with dbt-core#10547

If dbt ships native macro unit testing, specdbt should be able to adopt it
without a rewrite — that's the reason for the `NativeTestCompiler` registry
(§3) existing as a seam now, even with its macro slot empty. Adding
`MacroUnitTestCompiler` later means implementing one class against an
interface that already exists; the Gherkin frontend, fixtures, assertions,
and reporter don't change — the same shape Phase 0's `ExecutionAdapter` used
to absorb this entire Phase 1 rewrite without the layers above it changing.

### 5.5 Integration tier is not a stopgap

Once a native macro unit test exists, the ephemeral-schema mechanism doesn't
get deleted — it stays available for both models and macros, because it
proves something a mocked/CTE-injected unit test structurally can't: real
adapter round-trip behavior (actual warehouse-side type coercion, actual
DDL/permission behavior, actual incremental-merge behavior end-to-end). Unit
and integration tiers are two different guarantees, not two implementations
of the same guarantee at different speeds.

## 6. Gherkin grammar additions

- Models: `When the "<model_name>" model runs` — unchanged from Phase 0.
- Macros (new): `When the "{{ dbt_utils.generate_surrogate_key(['order_id',
  'customer_id']) }}" macro runs` — real Jinja verbatim, not a specdbt DSL.
- Incremental models (new): `Given the following rows already in "<model>"` →
  `input: this` (§4).
- Tags (new, all reuse standard Gherkin tag syntax, nothing invented):
  - `@unit` / `@integration` — explicit tier selection, overriding the
    resource-kind default from §3.
  - `@adapter:<name>` — optional, restricts a scenario to a specific adapter
    when its behavior is genuinely adapter-specific.
  - `@ai-generated` — provenance marker for the Phase 3 "AI proposes, human
    approves" rule (original vision doc): an AI-authored scenario carries this
    tag until a human reviews and removes it. Not implemented in Phase 1 (no
    AI generation exists yet) — reserved now so Phase 3 has a place to land.

## 7. Readable by both humans and machines — without inventing a dialect

Grounded in Cucumber's own official docs
(`cucumber.io/docs/bdd`, `cucumber.io/docs/bdd/better-gherkin`), not guessed:
BDD's stated premise is specifications "readable by both humans and
computers." No AI-specific Cucumber guidance exists yet (checked); the
mechanisms below are official Gherkin features specdbt just hadn't used.

- **Declarative, not imperative — mandatory, not a suggestion.** Cucumber's
  own before/after example contrasts `Given I type "x" in the email field /
  And I press "Submit"` (imperative, implementation detail) against `Given
  Free Frieda has a free subscription / When Free Frieda logs in` (declarative,
  intent). This is the same property that makes a scenario good context for
  an LLM to reason over or extend by analogy, and good "living documentation"
  for a non-technical reader — one property, not two. Codified as a rule in a
  new `docs/gherkin-style-guide.md`, checked when reviewing example/community
  contributions.
- **Doc strings with content-type annotations** (` ```markdown `, ` ```json `)
  — official Gherkin feature, reserved for scenarios needing a larger
  structured expected-payload blob, where it's clearer than a sprawling data
  table.
- **New `specdbt docs` CLI command** — Cucumber's own term for this is "living
  documentation." Renders a project's `.feature` files into one structured
  Markdown artifact, grouped by Feature/tag, annotated with last-run
  pass/fail freshness — built on the `FeatureReport`/`render_feature_report`
  structures Phase 0 already shipped, so this is genuinely small net-new work,
  not a new subsystem.

**Principle stated explicitly for contributors:** the AI-readiness story here
is "write good standard Gherkin," not "invent an AI-specific dialect."

## 8. Example projects

Replaces the data-pulse dogfood examples (kept in git history only):

- **jaffle_shop** (dbt Labs' official multi-adapter demo project, DuckDB-
  runnable out of the box) — model scenarios, unit tier.
- **dbt_utils** (dbt Labs' official macro package) — macro scenarios,
  integration tier. Its macros are explicitly `adapter.dispatch`-based (e.g.
  `generate_surrogate_key`, `date_trunc`, `star`) — the exact cross-warehouse
  macro shape this phase exists to prove against. `star()` additionally
  exercises the "introspective macros are in scope" claim from §5.2.

## 9. New dependencies (need the Phase 0 security check before install)

- `dbt-core` (PyPI)
- `dbt-duckdb` (PyPI)
- `dbt_utils` — installed via the target project's `packages.yml`, not PyPI.
  Different supply-chain surface (dbt Hub / git-based package resolution, not
  pip) — needs its own short note in the security review rather than being
  silently treated as covered by the PyPI checks above.

## 10. What changes vs. Phase 0's `ExecutionAdapter`

Phase 0's own Phase 1 doc named this explicitly as a signal worth flagging:
"if either [adapter] needs to change [the `run_model`] interface, that's a
signal the Phase 0 abstraction has a gap worth naming before writing more code
against it." It does change:

- `run_model(model_name, fixtures) -> ExecutionResult` — signature unchanged,
  semantics unchanged (still integration-tier real execution).
- `run_macro(macro_call, fixtures) -> ExecutionResult` — new abstract method.
- New parallel interface `NativeTestCompiler` (§3) for the unit tier — not an
  `ExecutionAdapter` method, since delegating-to-dbt's-own-runner and
  driving-real-execution-directly are different enough operations that
  overloading one interface with both would blur what each call actually does.

## 11. CI story

A GitHub Actions workflow is included in this repo (inert until a remote
exists — this project stays local-only per the standing "never push" rule;
the workflow file documents intent and is ready the day that changes). It
runs the DuckDB-target example suite only, since that's the one adapter with
no live-credential requirement.

## 12. Definition of Done for Phase 1

- `specdbt run` executes at least 3 jaffle_shop model scenarios via the unit
  tier (`unit_tests:` + `dbt test`), including one incremental-model scenario
  exercising both `is_incremental` branches.
- `specdbt run` executes at least 2 dbt_utils macro scenarios via the
  integration tier, including one exercising an introspective macro
  (`star()`), with schema teardown verified (no leftover `specdbt_*` schema
  after a run, pass or fail).
- `specdbt docs` renders a living-documentation Markdown artifact from the
  example scenarios.
- `docs/gherkin-style-guide.md` exists and the example scenarios conform to
  it (declarative, not imperative).
- All new dependencies security-checked and reported before install, per
  Phase 0's rule.
- Existing 60 Phase 0 tests plus new Phase 1 tests pass; `ruff` clean.
- Nothing pushed; still no git remote configured.
