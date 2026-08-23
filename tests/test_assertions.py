import pytest

from specdbt.adapters.base import ExecutionResult
from specdbt.assertions import (
    AssertionFailure,
    ThenContext,
    UnrecognizedStepError,
    evaluate_then_step,
)


@pytest.fixture
def sample_result():
    return ExecutionResult.of(
        rows=[
            {"station_id": "BER-001", "source": "brightsky", "temp_c": 18.2},
            {"station_id": "BER-002", "source": "dwd_backup", "temp_c": 17.9},
        ]
    )


def test_row_count_passes(sample_result):
    ctx = ThenContext(results={"stg": sample_result}, last_model="stg")
    evaluate_then_step('"stg" should have 2 rows', ctx)


def test_row_count_fails(sample_result):
    ctx = ThenContext(results={"stg": sample_result}, last_model="stg")
    with pytest.raises(AssertionFailure):
        evaluate_then_step('"stg" should have 5 rows', ctx)


def test_not_null_passes(sample_result):
    ctx = ThenContext(results={"stg": sample_result}, last_model="stg")
    evaluate_then_step('column "source" in "stg" should not contain nulls', ctx)


def test_not_null_fails():
    result = ExecutionResult.of(rows=[{"source": None}])
    ctx = ThenContext(results={"stg": result}, last_model="stg")
    with pytest.raises(AssertionFailure):
        evaluate_then_step('column "source" in "stg" should not contain nulls', ctx)


def test_unique_passes(sample_result):
    ctx = ThenContext(results={"stg": sample_result}, last_model="stg")
    evaluate_then_step('column "station_id" in "stg" should be unique', ctx)


def test_unique_fails():
    result = ExecutionResult.of(rows=[{"station_id": "BER-001"}, {"station_id": "BER-001"}])
    ctx = ThenContext(results={"stg": result}, last_model="stg")
    with pytest.raises(AssertionFailure):
        evaluate_then_step('column "station_id" in "stg" should be unique', ctx)


def test_row_field_string_value_passes(sample_result):
    ctx = ThenContext(results={"stg": sample_result}, last_model="stg")
    evaluate_then_step('the row for station_id "BER-001" should have source "brightsky"', ctx)


def test_row_field_numeric_value_passes(sample_result):
    ctx = ThenContext(results={"stg": sample_result}, last_model="stg")
    evaluate_then_step('the row for station_id "BER-001" should have temp_c 18.2', ctx)


def test_row_field_fails_on_value_mismatch(sample_result):
    ctx = ThenContext(results={"stg": sample_result}, last_model="stg")
    with pytest.raises(AssertionFailure):
        evaluate_then_step('the row for station_id "BER-001" should have source "dwd_backup"', ctx)


def test_row_field_fails_when_no_row_matches_key(sample_result):
    ctx = ThenContext(results={"stg": sample_result}, last_model="stg")
    with pytest.raises(AssertionFailure):
        evaluate_then_step('the row for station_id "BER-999" should have source "brightsky"', ctx)


def test_unrecognized_step_raises():
    ctx = ThenContext(results={}, last_model=None)
    with pytest.raises(UnrecognizedStepError):
        evaluate_then_step("something nobody implemented", ctx)


def test_referencing_a_model_that_has_not_run_raises_assertion_failure():
    ctx = ThenContext(results={}, last_model=None)
    with pytest.raises(AssertionFailure):
        evaluate_then_step('"nope" should have 1 row', ctx)


def test_produces_rows_passes_on_exact_match():
    result = ExecutionResult.of(rows=[{"id": 1, "name": "a"}, {"id": 2, "name": "b"}])
    ctx = ThenContext(results={"m": result}, last_model="m")
    table = [["id", "name"], ["1", "a"], ["2", "b"]]
    evaluate_then_step('the "m" should produce the following rows:', ctx, table=table)


def test_produces_rows_fails_on_mismatch():
    result = ExecutionResult.of(rows=[{"id": 1, "name": "a"}])
    ctx = ThenContext(results={"m": result}, last_model="m")
    table = [["id", "name"], ["1", "ZZZ"]]
    with pytest.raises(AssertionFailure):
        evaluate_then_step('the "m" should produce the following rows:', ctx, table=table)


def test_produces_rows_requires_a_table():
    ctx = ThenContext(results={"m": ExecutionResult.of(rows=[])}, last_model="m")
    with pytest.raises(AssertionFailure):
        evaluate_then_step('the "m" should produce the following rows:', ctx, table=None)


def test_produces_rows_works_with_a_macro_call_as_the_name():
    result = ExecutionResult.of(rows=[{"a": 1}])
    ctx = ThenContext(results={"select 1 as a": result}, last_model="select 1 as a")
    table = [["a"], ["1"]]
    evaluate_then_step('the "select 1 as a" should produce the following rows:', ctx, table=table)
