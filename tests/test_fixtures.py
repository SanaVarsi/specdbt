import pytest

from specdbt.fixtures import FixtureBuildError, build_fixture
from specdbt.parser import Step


def test_builds_fixture_with_typed_rows():
    step = Step(
        keyword="Given",
        type="Context",
        text='the following rows in "raw_weather_stations":',
        table=[
            ["station_id", "temp_c", "is_valid"],
            ["BER-001", "18.2", "true"],
        ],
    )
    fixture = build_fixture(step)
    assert fixture.name == "raw_weather_stations"
    assert fixture.rows == [{"station_id": "BER-001", "temp_c": 18.2, "is_valid": True}]


def test_rejects_non_context_step():
    step = Step(keyword="When", type="Action", text="the model runs", table=[])
    with pytest.raises(FixtureBuildError):
        build_fixture(step)


def test_rejects_step_text_that_does_not_match_the_given_pattern():
    step = Step(
        keyword="Given",
        type="Context",
        text="something else entirely",
        table=[["a"], ["1"]],
    )
    with pytest.raises(FixtureBuildError):
        build_fixture(step)


def test_rejects_given_step_with_no_table():
    step = Step(
        keyword="Given",
        type="Context",
        text='the following rows in "raw_weather_stations":',
        table=[],
    )
    with pytest.raises(FixtureBuildError):
        build_fixture(step)
