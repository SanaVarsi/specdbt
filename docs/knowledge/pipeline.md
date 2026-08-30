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
