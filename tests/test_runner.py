from pathlib import Path

from specdbt.adapters.base import ExecutionResult
from specdbt.adapters.fake_adapter import FakeAdapter
from specdbt.native_unit_tests.compiler import CompilerRegistry, NativeTestCompiler
from specdbt.parser import Scenario
from specdbt.reporter import StepResult
from specdbt.runner import run_feature_file, run_feature_text

PASSING_SOURCE = """Feature: Dedup

  Scenario: One row survives
    Given the following rows in "raw_weather_stations":
      | station_id | source |
      | BER-001    | brightsky |
    When the "stg_weather_stations" model runs
    Then "stg_weather_stations" should have 1 row
    And the row for station_id "BER-001" should have source "brightsky"
"""


def test_run_feature_text_reports_all_passing_steps():
    adapter = FakeAdapter()
    adapter.register(
        "stg_weather_stations",
        ExecutionResult.of(rows=[{"station_id": "BER-001", "source": "brightsky"}]),
    )
    report = run_feature_text(PASSING_SOURCE, adapter)
    assert report.name == "Dedup"
    assert len(report.scenarios) == 1
    assert report.scenarios[0].passed is True
    assert len(report.scenarios[0].steps) == 4


FAILING_SOURCE = """Feature: F

  Scenario: Fails
    Given the following rows in "a":
      | c |
      | 1 |
    When the "m" model runs
    Then "m" should have 1 row
    And the row for c "1" should have c 1
"""


def test_run_feature_text_stops_scenario_at_first_failed_step():
    adapter = FakeAdapter()
    adapter.register("m", ExecutionResult.of(rows=[]))
    report = run_feature_text(FAILING_SOURCE, adapter)
    scenario = report.scenarios[0]
    assert scenario.passed is False
    assert len(scenario.steps) == 3  # Given, When, Then(fails) -- the And is never reached
    assert scenario.steps[-1].passed is False
    assert scenario.steps[-1].error is not None
    assert "expected" in scenario.steps[-1].error


UNREGISTERED_MODEL_SOURCE = """Feature: F

  Scenario: Missing model
    Given the following rows in "a":
      | c |
      | 1 |
    When the "missing" model runs
    Then "missing" should have 1 row
"""


def test_run_feature_text_reports_unregistered_model_as_a_failed_when_step():
    adapter = FakeAdapter()
    report = run_feature_text(UNREGISTERED_MODEL_SOURCE, adapter)
    scenario = report.scenarios[0]
    assert scenario.passed is False
    assert len(scenario.steps) == 2  # Given, When(fails) -- Then never reached
    assert scenario.steps[1].passed is False


MACRO_WHEN_SOURCE = """Feature: Macro when step

  Scenario: A macro call runs
    Given the following rows in "orders":
      | order_id | status |
      | 1        | placed |
    When the "select order_id from orders" macro runs
    Then "select order_id from orders" should have 1 row
"""


def test_run_feature_text_routes_macro_when_step_to_run_macro():
    adapter = FakeAdapter()
    adapter.register("select order_id from orders", ExecutionResult.of(rows=[{"order_id": 1}]))
    report = run_feature_text(MACRO_WHEN_SOURCE, adapter)
    assert report.scenarios[0].passed is True


def test_run_feature_text_reports_unregistered_macro_as_a_failed_when_step():
    adapter = FakeAdapter()
    report = run_feature_text(MACRO_WHEN_SOURCE, adapter)
    scenario = report.scenarios[0]
    assert scenario.passed is False
    assert scenario.steps[-1].passed is False


ROW_TABLE_THEN_SOURCE = """Feature: Row table then

  Scenario: Exact rows match
    Given the following rows in "orders":
      | order_id | status |
      | 1        | placed |
    When the "m" model runs
    Then the "m" should produce the following rows:
      | order_id | status  |
      | 1        | shipped |
"""


def test_run_feature_text_wires_step_table_into_row_table_then():
    adapter = FakeAdapter()
    adapter.register("m", ExecutionResult.of(rows=[{"order_id": 1, "status": "shipped"}]))
    report = run_feature_text(ROW_TABLE_THEN_SOURCE, adapter)
    assert report.scenarios[0].passed is True


def test_run_feature_file_reads_from_disk(tmp_path: Path):
    adapter = FakeAdapter()
    adapter.register("m", ExecutionResult.of(rows=[{"c": 1}]))
    feature_file = tmp_path / "x.feature"
    feature_file.write_text(
        "Feature: F\n\n"
        "  Scenario: S\n"
        '    Given the following rows in "a":\n'
        "      | c |\n"
        "      | 1 |\n"
        '    When the "m" model runs\n'
        '    Then "m" should have 1 row\n'
    )
    report = run_feature_file(feature_file, adapter)
    assert report.scenarios[0].passed is True


class _StubCompiler(NativeTestCompiler):
    def __init__(self, step_results):
        self._step_results = step_results

    def run(self, scenario: Scenario) -> list[StepResult]:
        return self._step_results


UNTAGGED_MODEL_SOURCE = """Feature: F

  Scenario: Untagged model scenario
    Given the following rows in "a":
      | c |
      | 1 |
    When the "m" model runs
    Then the "m" should produce the following rows:
      | c |
      | 1 |
"""


def test_untagged_model_scenario_defaults_to_unit_tier_when_a_compiler_is_registered():
    registry = CompilerRegistry()
    registry.register("model", _StubCompiler([StepResult("Then", "x", passed=True)]))
    adapter = FakeAdapter()  # never touched -- unit tier doesn't use the adapter
    report = run_feature_text(UNTAGGED_MODEL_SOURCE, adapter, registry)
    assert report.scenarios[0].passed is True


def test_untagged_model_scenario_uses_integration_tier_when_no_compiler_registered():
    registry = CompilerRegistry()  # no "model" compiler registered
    adapter = FakeAdapter()
    adapter.register("m", ExecutionResult.of(rows=[{"c": 1}]))
    report = run_feature_text(UNTAGGED_MODEL_SOURCE, adapter, registry)
    assert report.scenarios[0].passed is True  # ran through the real integration path


INTEGRATION_TAGGED_SOURCE = """Feature: F

  @integration
  Scenario: Explicitly integration-tagged
    Given the following rows in "a":
      | c |
      | 1 |
    When the "m" model runs
    Then the "m" should produce the following rows:
      | c |
      | 1 |
"""


def test_integration_tag_bypasses_a_registered_unit_compiler():
    registry = CompilerRegistry()
    registry.register(
        "model", _StubCompiler([StepResult("Then", "x", passed=False, error="should never run")])
    )
    adapter = FakeAdapter()
    adapter.register("m", ExecutionResult.of(rows=[{"c": 1}]))
    report = run_feature_text(INTEGRATION_TAGGED_SOURCE, adapter, registry)
    assert report.scenarios[0].passed is True  # used the adapter, not the stub compiler


UNIT_TAGGED_MACRO_SOURCE = """Feature: F

  @unit
  Scenario: Unit-tagged macro has nowhere to go
    Given the following rows in "orders":
      | order_id |
      | 1        |
    When the "select order_id from orders" macro runs
    Then the "select order_id from orders" should produce the following rows:
      | order_id |
      | 1        |
"""


def test_unit_tagged_macro_scenario_fails_clearly_with_no_macro_compiler_registered():
    registry = CompilerRegistry()  # macro slot never registered, spec §5.4
    adapter = FakeAdapter()
    report = run_feature_text(UNIT_TAGGED_MACRO_SOURCE, adapter, registry)
    scenario = report.scenarios[0]
    assert scenario.passed is False
    assert scenario.steps[0].error is not None
    assert "dbt-core#10547" in scenario.steps[0].error


def test_run_feature_text_without_a_registry_arg_still_works_integration_only():
    # backward compatibility: Plan A's own existing 2-arg call sites get an
    # implicit empty CompilerRegistry(), so every scenario resolves to the
    # integration tier exactly as it did before this plan.
    adapter = FakeAdapter()
    adapter.register("m", ExecutionResult.of(rows=[{"c": 1}]))
    report = run_feature_text(UNTAGGED_MODEL_SOURCE, adapter)
    assert report.scenarios[0].passed is True


GRACEFUL_DEGRADATION_SOURCE = """Feature: F

  Scenario: Malformed, missing a When step
    Given the following rows in "a":
      | c |
      | 1 |
    Then "a" should have 1 row

  Scenario: Well-formed, should still run
    Given the following rows in "a":
      | c |
      | 1 |
    When the "m" model runs
    Then the "m" should produce the following rows:
      | c |
      | 1 |
"""


def test_a_malformed_scenario_fails_gracefully_without_crashing_the_whole_run():
    registry = CompilerRegistry()  # no "model" compiler -- both scenarios resolve integration
    adapter = FakeAdapter()
    adapter.register("m", ExecutionResult.of(rows=[{"c": 1}]))
    report = run_feature_text(GRACEFUL_DEGRADATION_SOURCE, adapter, registry)  # must not raise
    assert report.scenarios[0].passed is False
    assert report.scenarios[1].passed is True
