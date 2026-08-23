"""Wires parser -> fixtures -> adapter -> assertions -> reporter into one
pipeline (spec: docs/superpowers/specs/2026-08-23-specdbt-phase0-design.md)."""

from __future__ import annotations

import re
from pathlib import Path

from specdbt.adapters.base import ExecutionAdapter, ExecutionResult
from specdbt.assertions import ThenContext, evaluate_then_step
from specdbt.fixtures import Fixture, build_fixture
from specdbt.parser import Scenario, parse_feature_text
from specdbt.reporter import FeatureReport, ScenarioReport, StepResult

_WHEN_MODEL_RE = re.compile(r'the "([^"]+)" model runs$')


def run_feature_text(source: str, adapter: ExecutionAdapter) -> FeatureReport:
    feature = parse_feature_text(source)
    scenario_reports = [_run_scenario(scenario, adapter) for scenario in feature.scenarios]
    return FeatureReport(name=feature.name, scenarios=scenario_reports)


def run_feature_file(path: Path, adapter: ExecutionAdapter) -> FeatureReport:
    return run_feature_text(Path(path).read_text(), adapter)


def _run_scenario(scenario: Scenario, adapter: ExecutionAdapter) -> ScenarioReport:
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
                match = _WHEN_MODEL_RE.search(step.text)
                if match is None:
                    raise ValueError(f"no When-step pattern matches: {step.text!r}")
                model_name = match.group(1)
                results[model_name] = adapter.run_model(model_name, list(fixtures.values()))
                last_model = model_name
            else:  # "Outcome"
                evaluate_then_step(step.text, ThenContext(results=results, last_model=last_model))
        except Exception as exc:  # noqa: BLE001 -- any step-level error becomes a failed step
            step_results.append(StepResult(step.keyword, step.text, passed=False, error=str(exc)))
            break
        else:
            step_results.append(StepResult(step.keyword, step.text, passed=True))

    return ScenarioReport(name=scenario.name, steps=step_results)
