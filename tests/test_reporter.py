from specdbt.reporter import (
    FeatureReport,
    ScenarioReport,
    StepResult,
    render_feature_report,
    render_summary,
)


def test_scenario_report_passed_is_true_when_all_steps_pass():
    scenario = ScenarioReport(name="S", steps=[StepResult("Given", "x", True)])
    assert scenario.passed is True


def test_scenario_report_passed_is_false_when_any_step_fails():
    scenario = ScenarioReport(
        name="S", steps=[StepResult("Given", "x", True), StepResult("Then", "y", False, "boom")]
    )
    assert scenario.passed is False


def test_render_feature_report_shows_names_and_marks():
    report = FeatureReport(
        name="Weather source deduplication",
        scenarios=[
            ScenarioReport(
                name="One row survives",
                steps=[
                    StepResult("Given", "some rows", True),
                    StepResult("Then", "it fails", False, "expected 1, got 2"),
                ],
            )
        ],
    )
    text = render_feature_report(report)
    assert "Feature: Weather source deduplication" in text
    assert "Scenario: One row survives" in text
    assert "✓" in text
    assert "✗" in text
    assert "expected 1, got 2" in text


def test_render_summary_counts_scenarios_steps_and_failures():
    report = FeatureReport(
        name="F",
        scenarios=[
            ScenarioReport(
                name="S1",
                steps=[StepResult("Given", "a", True), StepResult("Then", "b", False, "x")],
            ),
            ScenarioReport(name="S2", steps=[StepResult("Given", "a", True)]),
        ],
    )
    assert render_summary([report]) == "2 scenario(s), 3 step(s), 1 failure(s)"
