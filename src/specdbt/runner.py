"""Wires parser -> fixtures -> adapter -> assertions -> reporter into one
pipeline (spec: docs/superpowers/specs/2026-08-23-specdbt-phase0-design.md,
2026-08-23-specdbt-phase1-design-v2.md §3/§10). Tier resolution (spec §3)
picks, per scenario, between two entirely different control paths: the
integration tier below executes step-by-step, threading results forward as
each step runs; the unit tier hands the WHOLE scenario to a
NativeTestCompiler, since dbt's own unit-test runner does the given/when/
then work itself -- the Then step's table there is an *input* to
compilation, read before anything executes, not a check performed after.
"""

from __future__ import annotations

import re
from pathlib import Path

from specdbt.adapters.base import ExecutionAdapter, ExecutionResult
from specdbt.assertions import ThenContext, evaluate_then_step
from specdbt.fixtures import Fixture, build_fixture
from specdbt.native_unit_tests.compiler import (
    CompilerRegistry,
    get_compiler_or_raise,
    resolve_tier,
)
from specdbt.parser import Scenario, parse_feature_text
from specdbt.reporter import FeatureReport, ScenarioReport, StepResult

_WHEN_MODEL_RE = re.compile(r'the "([^"]+)" model runs$')
_WHEN_MACRO_RE = re.compile(r'the "(.+)" macro runs$')


def run_feature_text(
    source: str, adapter: ExecutionAdapter, compiler_registry: CompilerRegistry | None = None
) -> FeatureReport:
    feature = parse_feature_text(source)
    registry = compiler_registry if compiler_registry is not None else CompilerRegistry()
    scenario_reports = [
        _run_scenario(scenario, adapter, registry) for scenario in feature.scenarios
    ]
    return FeatureReport(name=feature.name, scenarios=scenario_reports)


def run_feature_file(
    path: Path, adapter: ExecutionAdapter, compiler_registry: CompilerRegistry | None = None
) -> FeatureReport:
    return run_feature_text(Path(path).read_text(), adapter, compiler_registry)


def _detect_resource_kind(scenario: Scenario) -> str:
    for step in scenario.steps:
        if step.type == "Action":
            if _WHEN_MODEL_RE.search(step.text) is not None:
                return "model"
            if _WHEN_MACRO_RE.search(step.text) is not None:
                return "macro"
            raise ValueError(f"no When-step pattern matches: {step.text!r}")
    raise ValueError(f'scenario "{scenario.name}" has no When step')


def _run_scenario(
    scenario: Scenario, adapter: ExecutionAdapter, registry: CompilerRegistry
) -> ScenarioReport:
    try:
        resource_kind = _detect_resource_kind(scenario)
        tier = resolve_tier(scenario.tags, resource_kind, registry)
    except Exception as exc:  # noqa: BLE001 -- a malformed scenario becomes one failed scenario, not a crashed run
        return ScenarioReport(
            name=scenario.name,
            steps=[StepResult("Scenario", scenario.name, passed=False, error=str(exc))],
        )

    if tier == "unit":
        try:
            compiler = get_compiler_or_raise(registry, resource_kind)
            step_results = compiler.run(scenario)
        except Exception as exc:  # noqa: BLE001 -- any compile/run error becomes one failed step
            step_results = [StepResult("Scenario", scenario.name, passed=False, error=str(exc))]
        return ScenarioReport(name=scenario.name, steps=step_results)

    return _run_integration_tier_scenario(scenario, adapter)


def _run_integration_tier_scenario(scenario: Scenario, adapter: ExecutionAdapter) -> ScenarioReport:
    fixtures: dict[str, Fixture] = {}
    results: dict[str, ExecutionResult] = {}
    last_model: str | None = None
    step_results: list[StepResult] = []

    for step in scenario.steps:
        try:
            if step.type == "Context":
                fixture = build_fixture(step)
                fixtures[fixture.name] = fixture
            elif step.type == "Action":
                model_match = _WHEN_MODEL_RE.search(step.text)
                if model_match is not None:
                    model_name = model_match.group(1)
                    results[model_name] = adapter.run_model(model_name, list(fixtures.values()))
                    last_model = model_name
                else:
                    macro_match = _WHEN_MACRO_RE.search(step.text)
                    if macro_match is None:
                        raise ValueError(f"no When-step pattern matches: {step.text!r}")
                    macro_call = macro_match.group(1)
                    results[macro_call] = adapter.run_macro(macro_call, list(fixtures.values()))
                    last_model = macro_call
            else:  # "Outcome"
                evaluate_then_step(
                    step.text,
                    ThenContext(results=results, last_model=last_model),
                    table=step.table or None,
                )
        except Exception as exc:  # noqa: BLE001 -- any step-level error becomes a failed step
            step_results.append(StepResult(step.keyword, step.text, passed=False, error=str(exc)))
            break
        else:
            step_results.append(StepResult(step.keyword, step.text, passed=True))

    return ScenarioReport(name=scenario.name, steps=step_results)
