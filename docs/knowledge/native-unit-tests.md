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
