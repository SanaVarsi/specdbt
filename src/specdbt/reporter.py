"""Terminal reporting: echoes scenarios back in their own Gherkin language,
with a pass/fail mark and error detail per step."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StepResult:
    keyword: str
    text: str
    passed: bool
    error: str | None = None


@dataclass
class ScenarioReport:
    name: str
    steps: list[StepResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(step.passed for step in self.steps)


@dataclass
class FeatureReport:
    name: str
    scenarios: list[ScenarioReport] = field(default_factory=list)


def render_feature_report(report: FeatureReport) -> str:
    lines = [f"Feature: {report.name}", ""]
    for scenario in report.scenarios:
        lines.append(f"  Scenario: {scenario.name}")
        for step in scenario.steps:
            mark = "✓" if step.passed else "✗"
            lines.append(f"    {step.keyword} {step.text}   {mark}")
            if not step.passed and step.error:
                lines.append(f"        {step.error}")
        lines.append("")
    return "\n".join(lines)


def render_summary(reports: list[FeatureReport]) -> str:
    scenario_count = sum(len(r.scenarios) for r in reports)
    steps = [step for r in reports for scenario in r.scenarios for step in scenario.steps]
    failures = sum(1 for step in steps if not step.passed)
    return f"{scenario_count} scenario(s), {len(steps)} step(s), {failures} failure(s)"
