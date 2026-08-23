"""Phase 0's only concrete adapter: returns pre-registered canned results,
never computes anything from the fixtures it's given. Proves the pipeline
plumbing; DbtExecutionAdapter (Phase 1) provides real correctness for macros.
"""

from __future__ import annotations

from specdbt.adapters.base import ExecutionAdapter, ExecutionResult
from specdbt.fixtures import Fixture


class ModelNotRegisteredError(KeyError):
    """Raised when run_model()/run_macro() is asked for a name with no
    canned result registered."""


class FakeAdapter(ExecutionAdapter):
    def __init__(self) -> None:
        self._canned_results: dict[str, ExecutionResult] = {}

    def register(self, name: str, result: ExecutionResult) -> None:
        """Registers a canned result under `name` -- a model name
        (run_model) or the exact macro-call string a scenario's When step
        uses (run_macro). Same registry either way; FakeAdapter doesn't
        distinguish between the two kinds of caller."""
        self._canned_results[name] = result

    def run_model(self, model_name: str, fixtures: list[Fixture]) -> ExecutionResult:
        return self._lookup(model_name)

    def run_macro(self, macro_call: str, fixtures: list[Fixture]) -> ExecutionResult:
        return self._lookup(macro_call)

    def _lookup(self, name: str) -> ExecutionResult:
        try:
            return self._canned_results[name]
        except KeyError:
            raise ModelNotRegisteredError(f"no canned result registered for {name!r}") from None
