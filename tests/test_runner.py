from pathlib import Path

from specdbt.adapters.base import ExecutionResult
from specdbt.adapters.fake_adapter import FakeAdapter
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
