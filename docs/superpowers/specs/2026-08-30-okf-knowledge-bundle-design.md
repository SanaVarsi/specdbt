# OKF Knowledge Bundle + /specdbt Skill — Design

## Goal

Give specdbt a self-describing, agent-processable architecture reference
(Google's [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
v0.2), a `/specdbt` skill that loads it as context, and root-level
`AGENTS.md`/`CLAUDE.md` files so any coding agent (not just Claude Code)
discovers it. No pre-commit hook — out of scope for this pass.

## OKF conformance target

Minimal conformant bundle: every non-reserved `.md` has parseable YAML
frontmatter with a non-empty `type`. We use only `type`, `title`,
`description`, `tags` — no `sources`/`generated`/`verified` (no
provenance/trust claims are being made about who authored these docs).
`type` values are free text per spec (only "Attested Computation" is a
reserved type with required fields, which we don't use): `Architecture
Overview`, `Design Decision`, `Module`.

## Bundle layout — `docs/knowledge/`

```
docs/knowledge/
  index.md              # okf_version: "0.2" frontmatter only; links below
  pipeline.md            # Architecture Overview
  two-tier-design.md     # Design Decision
  adapters.md            # Module
  dbt-integration.md     # Module
  native-unit-tests.md   # Module
  cli.md                 # Module
  ai.md                  # Module
```

No `log.md` — nothing to backfill as history yet.

### Content source

Content is authored from the existing repo (`src/specdbt/**`, `README.md`,
`docs/*.md`) plus the architecture summary already captured in project
memory (module map, two-tier split rationale, supporting-module
responsibilities). Each doc cross-links related concepts via OKF-style
bundle-relative links (`/docs/knowledge/<file>.md`).

Per-file scope:

- **`pipeline.md`** — `.feature` file to `parser.py` to `runner.py` to
  `fixtures.py` to `adapters/*` to `assertions.py` to `reporter.py`; where
  `cli.py` fits (click entrypoint: `init`, `run --engine fake|dbt`).
- **`two-tier-design.md`** — `resolve_tier()` selection logic, integration
  tier (step-by-step via `DbtExecutionAdapter`) vs unit tier (whole-scenario
  compile to native `dbt` `unit_tests:` YAML), why model integration-tier
  execution deliberately raises rather than faking `ref()` substitution.
- **`adapters.md`** — `ExecutionAdapter` ABC + `ExecutionResult`,
  `fake_adapter.py` (canned results), `prod_guard.py` (shared prod-schema
  guard).
- **`dbt-integration.md`** — macro-tier adapter-dispatch plumbing:
  `macro_file.py`, `fixture_sql.py`, `ref_substitution.py`,
  `relation_expr.py`, `target_catalog.py`, and how `DbtExecutionAdapter
  .run_macro()` threads a resolved catalog through them.
- **`native-unit-tests.md`** — `model_unit_test_compiler.py` +
  `model_compiler.py` + `yaml_file.py` path: scenario to generated YAML
  to `dbt test --select unit_test:...` to translated pass/fail.
- **`cli.md`** — click entrypoint surface.
- **`ai.md`** — `ai/` package, all stubs raising `NotImplementedError`
  (unbuilt Phase 3), flagged so agents don't mistake it for dead code to
  delete.

## /specdbt skill — .claude/skills/specdbt/SKILL.md

Frontmatter `description` names it as the specdbt architecture knowledge
base entry point. Body instructs the invoking agent to:

1. Read `docs/knowledge/index.md`, then read each linked concept doc.
2. Answer the user's question grounded in that bundle rather than a fresh
   `grep`/read of `src/`.
3. Before finishing, ask the user whether any concept doc looks stale
   against current `src/` state, and offer to update it if so (no
   automatic rewriting).

## Root agent-discovery files

- **`AGENTS.md`** (new, agent-agnostic): one paragraph pointing any coding
  agent at `docs/knowledge/` as the architecture source of truth, plus
  existing repo conventions worth surfacing (tests mirror `src/` 1:1 under
  `tests/`, Gherkin style guide at `docs/gherkin-style-guide.md`).
- **`CLAUDE.md`** (new, repo root, distinct from the user's private
  global `~/.claude/CLAUDE.md`): `@AGENTS.md` import line, plus a note that
  `/specdbt` loads the knowledge bundle on demand.

## Out of scope

- Pre-commit hook enforcing doc freshness (explicitly deferred).
- Per-function/class API docs (architecture-level only, per user choice).
- OKF `sources`/`generated`/`verified` provenance fields.
