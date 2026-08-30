# OKF Knowledge Bundle + /specdbt Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give specdbt an OKF v0.2 knowledge bundle documenting its
architecture, a `/specdbt` skill that loads it as context on demand, and
root `AGENTS.md`/`CLAUDE.md` files so any coding agent discovers it.

**Architecture:** Pure content-authoring feature — no application code
changes. Seven Markdown concept docs + one index under `docs/knowledge/`
(OKF v0.2 bundle), one Claude skill definition under
`.claude/skills/specdbt/`, and two new root Markdown files. Each task's
"test" is an automated frontmatter-conformance check (parseable YAML,
non-empty `type`) run via a one-line `python -c` invocation — no pytest
suite, since these are docs, not source.

**Tech Stack:** Markdown, YAML frontmatter, PyYAML (already a transitive
dep via dbt; falls back to stdlib-free manual check if unavailable — see
Task 1).

**Spec:** `docs/superpowers/specs/2026-08-30-okf-knowledge-bundle-design.md`

## Global Constraints

- OKF frontmatter fields used: `type`, `title`, `description`, `tags`
  only. Never add `sources`, `generated`, `verified` (no provenance/trust
  claims per spec).
- `type` is free text (spec requires only non-empty); use exactly
  `Architecture Overview`, `Design Decision`, or `Module` per file below.
- Cross-links between concept docs use OKF bundle-relative absolute form:
  `/docs/knowledge/<file>.md`.
- No pre-commit hook, no per-function API docs — explicitly out of scope.
- Root `index.md` frontmatter is `okf_version: "0.2"` only — no `type`
  field (index/log files are OKF-reserved, not concepts).

---

### Task 1: Bundle root — `index.md` + conformance check + `pipeline.md`

**Files:**
- Create: `docs/knowledge/index.md`
- Create: `docs/knowledge/pipeline.md`
- Test: none (manual conformance check, see steps)

**Interfaces:**
- Produces: the bundle directory `docs/knowledge/` that all later tasks
  add files into; the link target list every concept doc cross-links
  against (`/docs/knowledge/index.md`, `/docs/knowledge/pipeline.md`,
  `/docs/knowledge/two-tier-design.md`, `/docs/knowledge/adapters.md`,
  `/docs/knowledge/dbt-integration.md`,
  `/docs/knowledge/native-unit-tests.md`, `/docs/knowledge/cli.md`,
  `/docs/knowledge/ai.md`).

- [ ] **Step 1: Create `docs/knowledge/index.md`**

```markdown
---
okf_version: "0.2"
---

# specdbt Knowledge Bundle

Architecture reference for the specdbt codebase, in [Open Knowledge
Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
v0.2. Each linked file below is a concept document: a `type` in its
frontmatter, prose in its body, cross-links to related concepts.

* [Pipeline](pipeline.md) - end-to-end flow from `.feature` file to
  terminal report
* [Two-Tier Design](two-tier-design.md) - unit vs integration tier split,
  the core execution decision
* [Adapters](adapters.md) - `ExecutionAdapter` boundary and its
  implementations
* [dbt Integration](dbt-integration.md) - macro-tier adapter-dispatch
  plumbing
* [Native Unit Tests](native-unit-tests.md) - model unit-tier compiler
* [CLI](cli.md) - click entrypoint
* [AI Stubs](ai.md) - unbuilt Phase 3 package
```

- [ ] **Step 2: Create `docs/knowledge/pipeline.md`**

```markdown
---
type: Architecture Overview
title: specdbt Execution Pipeline
description: How a .feature file becomes a pass/fail report.
tags: [pipeline, architecture]
---

# specdbt Execution Pipeline

specdbt runs a Gherkin `.feature` file through a fixed pipeline of
single-purpose modules:

```
.feature file
  -> parser.py            Gherkin text -> Feature/Scenario/Step dataclasses
                           (wraps the gherkin-official library)
  -> runner.py             orchestrates per-scenario: picks a tier, drives it
  -> fixtures.py           Given step -> Fixture(name, rows)
  -> adapters/*            executes the model/macro, returns ExecutionResult(rows)
  -> assertions.py         Then step text + table -> pass/fail
  -> reporter.py           StepResult/ScenarioReport/FeatureReport -> terminal echo
```

`parser.py` exposes `parse_feature_text(source: str) -> Feature` and
`parse_feature_file(path: Path) -> Feature`, producing `Feature` /
`Scenario` / `Step` dataclasses. A parse error raises
`FeatureParseError`.

`runner.py` exposes `run_feature_text(...)` and `run_feature_file(...)`
as the two public entrypoints. Per scenario, `_detect_resource_kind`
decides whether the scenario targets a model or a macro, then dispatch
picks a tier (see [Two-Tier Design](two-tier-design.md)) and either runs
it step-by-step (`_run_integration_tier_scenario`, using an
[`ExecutionAdapter`](adapters.md)) or hands the whole scenario to a
[native test compiler](native-unit-tests.md).

`fixtures.py::build_fixture(step: Step) -> Fixture` turns a parsed
`Given` step's table into a `Fixture(name, rows)`. `FixtureBuildError` on
malformed input.

`assertions.py::evaluate_then_step(text, ctx, table=None) -> None` checks
a `Then` step against a `ThenContext` (which holds executed results by
model/macro name); raises `AssertionFailure` (carrying `expected`/
`actual`) on mismatch, `UnrecognizedStepError` for unknown step text. Row
assertions do column-projection + multiset comparison
(`collections.Counter`), not exact row-order — this mirrors dbt's own
unit-test semantics.

`reporter.py` collects `StepResult` into `ScenarioReport` (exposes
`.passed`) into `FeatureReport`, and renders both a per-feature report
(`render_feature_report`) and a cross-feature summary
(`render_summary`).

The CLI (see [CLI](cli.md)) is the process entrypoint that calls into
`runner.py`.
```

- [ ] **Step 3: Verify both files' frontmatter is valid OKF**

Run:
```bash
python3 -c "
import re
import yaml
from pathlib import Path

for name, requires_type in [('index.md', False), ('pipeline.md', True)]:
    p = Path('docs/knowledge') / name
    text = p.read_text()
    m = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
    assert m, f'{name}: no frontmatter block'
    fm = yaml.safe_load(m.group(1))
    if requires_type:
        assert fm.get('type'), f'{name}: missing/empty type'
    else:
        assert fm.get('okf_version') == '0.2', f'{name}: bad okf_version'
    print(f'{name}: OK ({fm})')
"
```
Expected: both files print `OK` with their parsed frontmatter dict.

- [ ] **Step 4: Commit**

```bash
git add docs/knowledge/index.md docs/knowledge/pipeline.md
git commit -m "docs: add OKF bundle root and pipeline concept doc"
```

---

### Task 2: `two-tier-design.md`

**Files:**
- Create: `docs/knowledge/two-tier-design.md`

**Interfaces:**
- Consumes: nothing from other tasks (self-contained doc); links to
  `/docs/knowledge/pipeline.md` and `/docs/knowledge/adapters.md` created
  in Task 1 and Task 3.

- [ ] **Step 1: Create `docs/knowledge/two-tier-design.md`**

```markdown
---
type: Design Decision
title: Unit vs Integration Tier Split
description: How specdbt decides whether a scenario runs step-by-step or via dbt's native unit-test mechanism, and why.
tags: [design-decision, tiers]
---

# Unit vs Integration Tier Split

This is specdbt's core design decision: every scenario runs through one
of two structurally different control flows, chosen per-scenario by
`native_unit_tests/compiler.py::resolve_tier(tags, resource_kind,
registry) -> str`. Selection rule: an explicit `@unit` or `@integration`
tag wins; otherwise default to unit if a `NativeTestCompiler` is
registered in the `CompilerRegistry` for that `resource_kind`, else
integration.

## Integration tier

Driven by `runner.py::_run_integration_tier_scenario(scenario, adapter)`.
specdbt builds fixtures from the `Given` steps, calls
`adapter.run_model()` / `adapter.run_macro()` (see
[Adapters](adapters.md)), threads the `ExecutionResult` forward, and
evaluates each `Then` step against it via `assertions.py`. The real
adapter, `DbtExecutionAdapter`, materializes fixtures as `CREATE TABLE AS
SELECT` into an ephemeral `specdbt_<uuid>` schema, textually substitutes
`ref()`/`source()` calls to point there, and runs the result via `dbt
show --inline` (see [dbt Integration](dbt-integration.md)).

## Unit tier

Driven by `native_unit_tests/model_unit_test_compiler.py::
ModelUnitTestCompiler.run(scenario) -> list[StepResult]`. The whole
scenario — not just individual steps — is compiled
(`model_compiler.py::compile_scenario(scenario) -> CompiledUnitTest`,
raising `UnitTestCompileError` on bad input) into dbt's own native
`unit_tests:` YAML (`yaml_file.py::render_unit_test_yaml` /
`write_unit_test_yaml`), written into the target project's model-paths
directory, then run via `dbt test --select unit_test:...`
(`_invoke_test`). Results translate back into `StepResult`s.
`ModelUnitTestCompiler` is only registered for models — macros have no
native dbt unit-test mechanism
([dbt-core#10547](https://github.com/dbt-labs/dbt-core/issues/10547),
still open as of this writing) — so an `@unit` tag on a macro scenario
raises `UnitTierNotSupportedError` from
`compiler.py::get_compiler_or_raise`.

## Why models can't fake integration tier

`DbtExecutionAdapter.run_model()` deliberately raises
`ModelIntegrationTierNotImplementedError` rather than attempting the
macro-tier's text-substitution trick. A model's `ref()` calls live inside
its own compiled SQL file, invisible to substitution done from outside —
faking model integration-tier execution would silently run against real
project state instead of the ephemeral test schema. Models are therefore
only ever tested for real via the unit tier.

## Why two control flows, not one interface

`NativeTestCompiler` (whole-scenario compile-and-delegate) is a
deliberately separate abstraction from `ExecutionAdapter` (step-by-step
execution) — they are not two backends behind a shared interface, because
their control flow shapes differ structurally, not just in
implementation detail.
```

- [ ] **Step 2: Verify frontmatter**

Run:
```bash
python3 -c "
import re, yaml
from pathlib import Path
text = Path('docs/knowledge/two-tier-design.md').read_text()
m = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
fm = yaml.safe_load(m.group(1))
assert fm.get('type') == 'Design Decision'
print('OK', fm)
"
```
Expected: prints `OK` with the frontmatter dict.

- [ ] **Step 3: Commit**

```bash
git add docs/knowledge/two-tier-design.md
git commit -m "docs: add two-tier design decision concept doc"
```

---

### Task 3: `adapters.md` + `dbt-integration.md`

**Files:**
- Create: `docs/knowledge/adapters.md`
- Create: `docs/knowledge/dbt-integration.md`

**Interfaces:**
- Consumes: links to `/docs/knowledge/two-tier-design.md` (Task 2).
- Produces: links other docs (Task 2, Task 4) point back to.

- [ ] **Step 1: Create `docs/knowledge/adapters.md`**

```markdown
---
type: Module
title: adapters/ — Execution Boundary
description: The ExecutionAdapter ABC and its implementations; the engine-agnostic seam between specdbt and a real dbt run.
tags: [module, adapters]
---

# adapters/ — Execution Boundary

`adapters/base.py` defines the engine-agnostic boundary:

- `ExecutionResult` — dataclass wrapping result rows; `ExecutionResult.of(rows,
  raw=None)` classmethod constructor.
- `ExecutionAdapter` (ABC) — two abstract methods, `run_model(model_name,
  fixtures) -> ExecutionResult` and `run_macro(macro_call, fixtures) ->
  ExecutionResult`. Every execution engine implements this pair.

## Implementations

- `adapters/fake_adapter.py::FakeAdapter` — canned-result adapter used by
  `--engine fake`. `register(name, result)` seeds a lookup table; `run_model`/
  `run_macro` return the registered `ExecutionResult` via `_lookup`, raising
  `ModelNotRegisteredError` (a `KeyError` subclass) if nothing was registered
  for that name. Backed by co-located `.canned.py` files exposing a
  `CANNED_RESULTS` dict, loaded by the CLI.
- `DbtExecutionAdapter` — the real adapter; see
  [dbt Integration](dbt-integration.md) for how it executes macros, and
  [Two-Tier Design](two-tier-design.md) for why it refuses to execute
  models directly.

## Shared guard

`adapters/prod_guard.py::guard_against_prod_target(target, allow_any_schema)`
is called by both `DbtExecutionAdapter` and `ModelUnitTestCompiler` before
running anything: raises `ProdSchemaGuardError` if `target` contains
`"prod"` and `allow_any_schema` is not set. One guard, shared by both
tiers, so a prod-target run can't slip through either path.
```

- [ ] **Step 2: Create `docs/knowledge/dbt-integration.md`**

```markdown
---
type: Module
title: dbt_integration/ — Macro-Tier Adapter Dispatch
description: The plumbing DbtExecutionAdapter.run_macro() uses to execute a macro for real against any dbt-supported warehouse.
tags: [module, dbt-integration, macro-tier]
---

# dbt_integration/ — Macro-Tier Adapter Dispatch

Supports the integration tier's macro execution (see
[Two-Tier Design](two-tier-design.md) and [Adapters](adapters.md)).
Adapter-dispatch based — not hardcoded to one warehouse's SQL dialect —
so it works across dbt's supported adapters (DuckDB, Postgres,
Databricks, ...).

- `macro_file.py` — builds the temporary `.sql` file that wraps the macro
  call for `dbt show --inline`. `setup_macro_name(run_id)` /
  `teardown_macro_name(run_id)` name the ephemeral schema's setup/teardown
  macros; `render_macro_file(...)` renders the file content;
  `write_macro_file(project_dir, run_id, content) -> Path` writes it;
  `delete_macro_file(path)` cleans it up. Schema create/drop goes through
  `adapter.create_schema`/`drop_schema` — not raw SQL — so it works on
  every dbt adapter.
- `fixture_sql.py::render_fixture_ctas(schema, fixture, *, database=None)`
  renders a `CREATE TABLE ... AS SELECT ... UNION ALL ...` for a
  `Fixture`, with each cell wrapped in a `dbt.cast(val, <type macro>)`
  call chosen by `_dbt_type_macro(values)` — this is what makes fixture
  loading cross-database rather than DuckDB-specific.
- `ref_substitution.py::substitute_fixture_refs(...)` regex-swaps
  `ref()`/`source()` calls in the macro-call text for
  `api.Relation.create(...)` calls pointing at the ephemeral schema.
- `relation_expr.py::relation_expr(...)` — shared Relation-text builder
  used by both `fixture_sql.py` and `ref_substitution.py`, so the two
  never drift on how a relation reference is rendered.
- `target_catalog.py::resolve_target_catalog(project_dir, profiles_dir,
  target) -> str | None` resolves the target's `catalog`/`database`/
  `dbname` from the raw dbt profile dict, once per run.

`DbtExecutionAdapter.run_macro()` resolves the catalog once via
`target_catalog.py` and threads that single value through
`fixture_sql.py` and `ref_substitution.py`, so every rendered SQL
statement in one run agrees on which catalog/database it targets.
```

- [ ] **Step 3: Verify frontmatter for both files**

Run:
```bash
python3 -c "
import re, yaml
from pathlib import Path
for name in ['adapters.md', 'dbt-integration.md']:
    text = (Path('docs/knowledge') / name).read_text()
    m = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
    fm = yaml.safe_load(m.group(1))
    assert fm.get('type') == 'Module', name
    print(name, 'OK', fm)
"
```
Expected: both print `OK`.

- [ ] **Step 4: Commit**

```bash
git add docs/knowledge/adapters.md docs/knowledge/dbt-integration.md
git commit -m "docs: add adapters and dbt-integration concept docs"
```

---

### Task 4: `native-unit-tests.md` + `cli.md` + `ai.md`

**Files:**
- Create: `docs/knowledge/native-unit-tests.md`
- Create: `docs/knowledge/cli.md`
- Create: `docs/knowledge/ai.md`

**Interfaces:**
- Consumes: links to `/docs/knowledge/two-tier-design.md` (Task 2),
  `/docs/knowledge/pipeline.md` (Task 1).
- Produces: the last three link targets `index.md` (Task 1) references —
  after this task every link in the bundle resolves to a real file.

- [ ] **Step 1: Create `docs/knowledge/native-unit-tests.md`**

```markdown
---
type: Module
title: native_unit_tests/ — Unit-Tier Compiler
description: Compiles a whole scenario into dbt's native unit_tests YAML and runs it via dbt test.
tags: [module, native-unit-tests, unit-tier]
---

# native_unit_tests/ — Unit-Tier Compiler

Implements the unit tier described in
[Two-Tier Design](two-tier-design.md).

- `compiler.py` — the tier-selection machinery: `NativeTestCompiler` (ABC,
  one method `run(scenario) -> list[StepResult]`), `CompilerRegistry`
  (`register(resource_kind, compiler)` / `get(resource_kind)`),
  `resolve_tier(tags, resource_kind, registry) -> str`, and
  `get_compiler_or_raise(registry, resource_kind)` (raises
  `UnitTierNotSupportedError` if nothing is registered for that kind).
- `model_compiler.py::compile_scenario(scenario) -> CompiledUnitTest`
  turns a `Scenario`'s Given/When/Then into the fields a unit-test YAML
  needs; raises `UnitTestCompileError` on unsupported scenario shapes.
- `yaml_file.py` renders and writes that YAML:
  `unit_test_name(run_id)` names it, `render_unit_test_yaml(...)` builds
  the text, `write_unit_test_yaml(...)` writes it into the target
  project's model-paths dir, `delete_unit_test_yaml(path)` cleans it up
  afterward.
- `model_unit_test_compiler.py::ModelUnitTestCompiler` is the
  `NativeTestCompiler` registered for models. Its `run(scenario)`
  ensures the project is prebuilt (`_ensure_project_prebuilt`), writes
  the compiled YAML, invokes `dbt test --select unit_test:...`
  (`_invoke_test` / `_raw_invoke`), and translates the dbt result back
  into `StepResult`s — raising `DbtInvocationError` if the `dbt`
  subprocess itself fails to run (as opposed to the test failing).

Only registered for models: macros have no native dbt unit-test
mechanism ([dbt-core#10547](https://github.com/dbt-labs/dbt-core/issues/10547)
still open), so `@unit` on a macro scenario raises
`UnitTierNotSupportedError`.
```

- [ ] **Step 2: Create `docs/knowledge/cli.md`**

```markdown
---
type: Module
title: cli.py — Command-Line Entrypoint
description: The click-based CLI surface that drives runner.py.
tags: [module, cli]
---

# cli.py — Command-Line Entrypoint

Click-based entrypoint, `cli()` group, with subcommands:

- `init(directory)` — scaffolds a new specdbt project layout.
- `run(...)` — the main command; `--engine fake|dbt` selects between
  `FakeAdapter` (loading canned results via `_load_canned_results(path)`,
  which reads a co-located `.canned.py`'s `CANNED_RESULTS` dict — see
  [Adapters](adapters.md)) and the real `DbtExecutionAdapter`. Calls into
  `runner.py` (see [Pipeline](pipeline.md)) to actually execute scenarios.
- `generate(from_model, fixtures_flag)` and `compile_(target, to_format)`
  — stubbed, not yet implemented.
```

- [ ] **Step 3: Create `docs/knowledge/ai.md`**

```markdown
---
type: Module
title: ai/ — Unbuilt Phase 3 Stubs
description: Placeholder AI-assist package; every function raises NotImplementedError. Not dead code — a planned phase.
tags: [module, ai, unbuilt]
---

# ai/ — Unbuilt Phase 3 Stubs

`ai/stubs.py` defines the intended future surface, all raising
`NotImplementedError`:

- `LLMClient.complete(prompt) -> str`
- `generate_fixtures(model_sql, schema, count=3) -> list[dict]`
- `scenario_from_text(description) -> str`
- `explain_failure(fixture, model_sql, diff) -> str`

This is a deliberate placeholder for a planned phase, not dead code —
don't delete it as unused.
```

- [ ] **Step 4: Verify frontmatter for all three files**

Run:
```bash
python3 -c "
import re, yaml
from pathlib import Path
for name in ['native-unit-tests.md', 'cli.md', 'ai.md']:
    text = (Path('docs/knowledge') / name).read_text()
    m = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
    fm = yaml.safe_load(m.group(1))
    assert fm.get('type') == 'Module', name
    print(name, 'OK', fm)
"
```
Expected: all three print `OK`.

- [ ] **Step 5: Verify every link in `index.md` now resolves**

Run:
```bash
python3 -c "
import re
from pathlib import Path
text = Path('docs/knowledge/index.md').read_text()
for target in re.findall(r'\]\(([^)]+\.md)\)', text):
    assert (Path('docs/knowledge') / target).exists(), target
print('all index.md links resolve')
"
```
Expected: prints `all index.md links resolve`.

- [ ] **Step 6: Commit**

```bash
git add docs/knowledge/native-unit-tests.md docs/knowledge/cli.md docs/knowledge/ai.md
git commit -m "docs: add native-unit-tests, cli, and ai concept docs"
```

---

### Task 5: `/specdbt` skill

**Files:**
- Create: `.claude/skills/specdbt/SKILL.md`

**Interfaces:**
- Consumes: the complete `docs/knowledge/` bundle from Tasks 1-4 (reads
  `index.md` and every linked concept doc at invocation time).

- [ ] **Step 1: Create `.claude/skills/specdbt/SKILL.md`**

```markdown
---
name: specdbt
description: Load specdbt's OKF architecture knowledge bundle (docs/knowledge/) as context before answering questions about this repo's design, then offer to refresh any doc that looks stale against current source.
---

# specdbt Knowledge Bundle

This repo's architecture reference lives in `docs/knowledge/`, an [Open
Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
v0.2 bundle. Use it instead of a fresh grep/read of `src/` when answering
questions about specdbt's design.

## Steps

1. Read `docs/knowledge/index.md`.
2. Read every concept doc it links to (`pipeline.md`,
   `two-tier-design.md`, `adapters.md`, `dbt-integration.md`,
   `native-unit-tests.md`, `cli.md`, `ai.md`).
3. Answer the user's question grounded in that bundle. If something the
   user asks about isn't covered, say so rather than guessing, and fall
   back to reading the relevant source under `src/specdbt/`.
4. Before finishing, check whether anything you read in `src/` while
   answering contradicts a concept doc. If so, tell the user which doc
   looks stale and offer to update it — don't rewrite it automatically.
```

- [ ] **Step 2: Verify skill frontmatter parses**

Run:
```bash
python3 -c "
import re, yaml
from pathlib import Path
text = Path('.claude/skills/specdbt/SKILL.md').read_text()
m = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
fm = yaml.safe_load(m.group(1))
assert fm.get('name') == 'specdbt'
assert fm.get('description')
print('OK', fm)
"
```
Expected: prints `OK` with the frontmatter dict.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/specdbt/SKILL.md
git commit -m "feat: add /specdbt skill loading the OKF knowledge bundle"
```

---

### Task 6: Root `AGENTS.md` + `CLAUDE.md`

**Files:**
- Create: `AGENTS.md`
- Create: `CLAUDE.md`

**Interfaces:**
- Consumes: `docs/knowledge/` (Tasks 1-4) and `.claude/skills/specdbt/`
  (Task 5) as the things these files point agents at.

- [ ] **Step 1: Create root `AGENTS.md`**

```markdown
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
```

- [ ] **Step 2: Create root `CLAUDE.md`**

```markdown
@AGENTS.md

Claude Code users: the `/specdbt` skill (`.claude/skills/specdbt/`) loads
the `docs/knowledge/` bundle referenced above as context on demand — use
it instead of re-reading `src/specdbt/` from scratch.
```

- [ ] **Step 3: Verify both files exist and `CLAUDE.md` imports `AGENTS.md`**

Run:
```bash
python3 -c "
from pathlib import Path
assert Path('AGENTS.md').exists()
claude_md = Path('CLAUDE.md').read_text()
assert '@AGENTS.md' in claude_md.splitlines()[0]
print('OK')
"
```
Expected: prints `OK`.

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md CLAUDE.md
git commit -m "docs: add root AGENTS.md/CLAUDE.md pointing agents at the knowledge bundle"
```
