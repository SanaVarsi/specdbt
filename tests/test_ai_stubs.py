import pytest

from specdbt.ai.stubs import LLMClient, explain_failure, generate_fixtures, scenario_from_text


def test_llm_client_complete_not_implemented():
    with pytest.raises(NotImplementedError):
        LLMClient().complete("hello")


def test_generate_fixtures_not_implemented():
    with pytest.raises(NotImplementedError):
        generate_fixtures("select 1", {"a": "int"})


def test_scenario_from_text_not_implemented():
    with pytest.raises(NotImplementedError):
        scenario_from_text("a scenario description")


def test_explain_failure_not_implemented():
    with pytest.raises(NotImplementedError):
        explain_failure({}, "select 1", {})
