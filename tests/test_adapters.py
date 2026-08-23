import pytest

from specdbt.adapters.base import ExecutionAdapter, ExecutionResult
from specdbt.adapters.fake_adapter import FakeAdapter, ModelNotRegisteredError
from specdbt.fixtures import Fixture


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


def test_fake_adapter_returns_registered_result():
    adapter = FakeAdapter()
    result = ExecutionResult.of(rows=[{"a": 1}])
    adapter.register("my_model", result)
    assert adapter.run_model("my_model", fixtures=[]) is result


def test_fake_adapter_raises_for_unregistered_model():
    adapter = FakeAdapter()
    with pytest.raises(ModelNotRegisteredError):
        adapter.run_model("missing_model", fixtures=[])


def test_fake_adapter_ignores_fixtures_content():
    adapter = FakeAdapter()
    result = ExecutionResult.of(rows=[{"a": 1}])
    adapter.register("m", result)
    fixture = Fixture(name="raw", rows=[{"x": 1}])
    assert adapter.run_model("m", fixtures=[fixture]) is result


def test_fake_adapter_run_macro_returns_registered_result():
    adapter = FakeAdapter()
    result = ExecutionResult.of(rows=[{"a": 1}])
    adapter.register("select 1 as a", result)
    assert adapter.run_macro("select 1 as a", fixtures=[]) is result


def test_fake_adapter_run_macro_raises_for_unregistered_call():
    adapter = FakeAdapter()
    with pytest.raises(ModelNotRegisteredError):
        adapter.run_macro("select 1", fixtures=[])
