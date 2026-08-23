from pathlib import Path

import pytest

from specdbt.parser import FeatureParseError, parse_feature_file, parse_feature_text

SAMPLE = '''Feature: Weather station deduplication

  Scenario: Duplicate rows collapse to one
    Given the following rows in "raw_weather_stations":
      | station_id | source     |
      | BER-001    | brightsky  |
    When the "stg_weather_stations" model runs
    Then "stg_weather_stations" should have 1 row
    And the row for station_id "BER-001" should have source "brightsky"
'''


def test_parses_feature_and_scenario_names():
    feature = parse_feature_text(SAMPLE)
    assert feature.name == "Weather station deduplication"
    assert len(feature.scenarios) == 1
    assert feature.scenarios[0].name == "Duplicate rows collapse to one"


def test_step_keywords_and_types_in_order():
    scenario = parse_feature_text(SAMPLE).scenarios[0]
    assert [s.keyword for s in scenario.steps] == ["Given", "When", "Then", "And"]
    assert [s.type for s in scenario.steps] == ["Context", "Action", "Outcome", "Outcome"]


def test_conjunction_step_inherits_previous_type():
    # the "And" step above follows a "Then" (Outcome) step and must inherit "Outcome"
    scenario = parse_feature_text(SAMPLE).scenarios[0]
    assert scenario.steps[3].type == "Outcome"
    assert scenario.steps[3].text == 'the row for station_id "BER-001" should have source "brightsky"'


def test_data_table_captured_as_raw_rows():
    scenario = parse_feature_text(SAMPLE).scenarios[0]
    assert scenario.steps[0].table == [
        ["station_id", "source"],
        ["BER-001", "brightsky"],
    ]


def test_step_without_table_has_empty_table():
    scenario = parse_feature_text(SAMPLE).scenarios[0]
    assert scenario.steps[1].table == []


def test_rejects_invalid_gherkin_syntax():
    with pytest.raises(FeatureParseError):
        parse_feature_text("this is not gherkin at all !!! ###")


def test_rejects_source_with_no_feature_keyword():
    with pytest.raises(FeatureParseError):
        parse_feature_text("")


def test_parse_feature_file_reads_from_disk(tmp_path: Path):
    feature_file = tmp_path / "example.feature"
    feature_file.write_text(SAMPLE)
    feature = parse_feature_file(feature_file)
    assert feature.name == "Weather station deduplication"
