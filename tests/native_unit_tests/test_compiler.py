import pytest

from specdbt.native_unit_tests.compiler import (
    CompilerRegistry,
    NativeTestCompiler,
    UnitTierNotSupportedError,
    get_compiler_or_raise,
    resolve_tier,
)
from specdbt.parser import Scenario
from specdbt.reporter import StepResult


class _StubCompiler(NativeTestCompiler):
    def run(self, scenario: Scenario) -> list[StepResult]:
        return [StepResult("Then", "stub", passed=True)]


def test_registry_get_returns_none_when_nothing_registered():
    registry = CompilerRegistry()
    assert registry.get("model") is None


def test_registry_get_returns_the_registered_compiler():
    registry = CompilerRegistry()
    compiler = _StubCompiler()
    registry.register("model", compiler)
    assert registry.get("model") is compiler


def test_resolve_tier_explicit_unit_tag_wins():
    registry = CompilerRegistry()  # nothing registered
    assert resolve_tier(["@unit"], "macro", registry) == "unit"


def test_resolve_tier_explicit_integration_tag_wins_over_a_registered_compiler():
    registry = CompilerRegistry()
    registry.register("model", _StubCompiler())
    assert resolve_tier(["@integration"], "model", registry) == "integration"


def test_resolve_tier_rejects_both_tags_at_once():
    registry = CompilerRegistry()
    with pytest.raises(ValueError):
        resolve_tier(["@unit", "@integration"], "model", registry)


def test_resolve_tier_defaults_to_unit_when_a_compiler_is_registered():
    registry = CompilerRegistry()
    registry.register("model", _StubCompiler())
    assert resolve_tier([], "model", registry) == "unit"


def test_resolve_tier_defaults_to_integration_when_no_compiler_is_registered():
    registry = CompilerRegistry()
    assert resolve_tier([], "macro", registry) == "integration"


def test_get_compiler_or_raise_returns_the_registered_compiler():
    registry = CompilerRegistry()
    compiler = _StubCompiler()
    registry.register("model", compiler)
    assert get_compiler_or_raise(registry, "model") is compiler


def test_get_compiler_or_raise_names_dbt_core_10547_for_an_unregistered_kind():
    registry = CompilerRegistry()
    with pytest.raises(UnitTierNotSupportedError, match="dbt-core#10547"):
        get_compiler_or_raise(registry, "macro")
