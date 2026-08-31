"""Execution adapter interface — the engine-agnostic boundary. Every concrete
adapter (FakeAdapter now; PolarsAdapter/DuckDBAdapter/DbtCoreAdapter later)
implements this and nothing above it needs to know which one is in use.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from specdbt.fixtures import Fixture


@dataclass
class ExecutionResult:
    rows: list[dict]
    row_count: int
    raw: object = None

    @classmethod
    def of(cls, rows: list[dict], raw: object = None) -> ExecutionResult:
        """Convenience constructor: row_count is derived from len(rows)."""
        return cls(rows=rows, row_count=len(rows), raw=raw)


class ExecutionAdapter(ABC):
    @abstractmethod
    def run_model(self, model_name: str, fixtures: list[Fixture]) -> ExecutionResult:
        """Run `model_name` with the given fixtures substituted for its
        refs/sources, and return the resulting rows."""
        raise NotImplementedError

    @abstractmethod
    def run_macro(self, macro_call: str, fixtures: list[Fixture]) -> ExecutionResult:
        """Run `macro_call` -- a complete, real Jinja/SQL query string (not
        just a macro call expression), with the given fixtures'
        ref()/source() substituted for their ephemeral relations -- and
        return the resulting rows."""
        raise NotImplementedError
