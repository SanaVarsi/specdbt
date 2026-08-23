import pytest

from specdbt.adapters.base import ExecutionAdapter, ExecutionResult


def test_execution_result_of_derives_row_count():
    result = ExecutionResult.of(rows=[{"a": 1}, {"a": 2}])
    assert result.row_count == 2
    assert result.raw is None


def test_execution_result_of_handles_empty_rows():
    result = ExecutionResult.of(rows=[])
    assert result.row_count == 0


def test_execution_adapter_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        ExecutionAdapter()  # type: ignore[abstract]
