"""Unit-tier orchestration interface (spec §3, §10) -- delegates to
whatever native fixture mechanism dbt ships for a given resource kind.
Deliberately not an ExecutionAdapter method: delegating-to-dbt's-own-runner
(this) and driving-real-execution-directly (ExecutionAdapter.run_macro) are
different enough operations that overloading one interface would blur what
each call actually does.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from specdbt.parser import Scenario
from specdbt.reporter import StepResult

TAG_UNIT = "@unit"
TAG_INTEGRATION = "@integration"


class NativeTestCompiler(ABC):
    @abstractmethod
    def run(self, scenario: Scenario) -> list[StepResult]:
        """Compile `scenario` to whatever dbt-native mechanism this
        resource kind supports, run it for real, and return one StepResult
        per originally-authored Given/When/Then step, in step order. May
        raise; callers translate any exception into a single failed
        StepResult."""
        raise NotImplementedError


class UnitTierNotSupportedError(NotImplementedError):
    """Raised when a scenario resolves to @unit for a resource kind with no
    registered NativeTestCompiler (spec §3, §5.4) -- today, macros: dbt has
    no native mechanism yet (dbt-core#10547, open)."""


class CompilerRegistry:
    """Explicit, per-caller registry -- not a module-level singleton,
    matching how ExecutionAdapter instances are already passed around
    explicitly rather than through global state."""

    def __init__(self) -> None:
        self._compilers: dict[str, NativeTestCompiler] = {}

    def register(self, resource_kind: str, compiler: NativeTestCompiler) -> None:
        self._compilers[resource_kind] = compiler

    def get(self, resource_kind: str) -> NativeTestCompiler | None:
        return self._compilers.get(resource_kind)


def resolve_tier(tags: list[str], resource_kind: str, registry: CompilerRegistry) -> str:
    """ "unit" if @unit tag present, "integration" if @integration tag
    present (a scenario tagged both is an error), else "unit" if a
    compiler is registered for `resource_kind`, else "integration" (spec
    §3). Does not itself check whether a "unit"-resolved resource_kind
    actually has a compiler registered -- see get_compiler_or_raise."""
    if TAG_UNIT in tags and TAG_INTEGRATION in tags:
        raise ValueError(f"scenario tagged both {TAG_UNIT} and {TAG_INTEGRATION}")
    if TAG_UNIT in tags:
        return "unit"
    if TAG_INTEGRATION in tags:
        return "integration"
    return "unit" if registry.get(resource_kind) is not None else "integration"


def get_compiler_or_raise(registry: CompilerRegistry, resource_kind: str) -> NativeTestCompiler:
    compiler = registry.get(resource_kind)
    if compiler is None:
        raise UnitTierNotSupportedError(
            f"@unit is not supported for {resource_kind} resources yet -- dbt "
            "has no native mechanism (dbt-core#10547 open); tag this scenario "
            "@integration instead."
        )
    return compiler
