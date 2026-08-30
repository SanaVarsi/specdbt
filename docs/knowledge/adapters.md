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
