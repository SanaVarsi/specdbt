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
