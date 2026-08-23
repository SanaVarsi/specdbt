"""Phase 0's only concrete adapter: returns pre-registered canned results,
never computes anything from the fixtures it's given. Proves the pipeline
plumbing; Phase 1's PolarsAdapter/DuckDBAdapter provide real correctness.
"""
from __future__ import annotations

from specdbt.adapters.base import ExecutionAdapter, ExecutionResult
from specdbt.fixtures import Fixture


class ModelNotRegisteredError(KeyError):
    """Raised when run_model() is asked for a model with no canned result registered."""


class FakeAdapter(ExecutionAdapter):
    def __init__(self) -> None:
        self._canned_results: dict[str, ExecutionResult] = {}

    def register(self, model_name: str, result: ExecutionResult) -> None:
        self._canned_results[model_name] = result

    def run_model(self, model_name: str, fixtures: list[Fixture]) -> ExecutionResult:
        try:
            return self._canned_results[model_name]
        except KeyError:
            raise ModelNotRegisteredError(
                f"no canned result registered for model {model_name!r}"
            ) from None
