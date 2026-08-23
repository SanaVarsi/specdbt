from pathlib import Path

import pytest

from specdbt.adapters.prod_guard import ProdSchemaGuardError
from specdbt.native_unit_tests.model_compiler import UnitTestCompileError
from specdbt.native_unit_tests.model_unit_test_compiler import (
    DbtInvocationError,
    ModelUnitTestCompiler,
)
from specdbt.parser import parse_feature_text

PASSING_SOURCE = """Feature: F

  @unit
  Scenario: Uppercases status
    Given the following rows in "upstream_model":
      | id | status |
      | 1  | placed |
    When the "downstream_model" model runs
    Then the "downstream_model" should produce the following rows:
      | id | status |
      | 1  | PLACED |
"""

FAILING_SOURCE = """Feature: F

  @unit
  Scenario: Wrong expectation
    Given the following rows in "upstream_model":
      | id | status |
      | 1  | placed |
    When the "downstream_model" model runs
    Then the "downstream_model" should produce the following rows:
      | id | status |
      | 1  | ZZZ    |
"""

BAD_MODEL_SOURCE = """Feature: F

  @unit
  Scenario: References a model that doesn't exist
    Given the following rows in "upstream_model":
      | id |
      | 1  |
    When the "does_not_exist" model runs
    Then the "does_not_exist" should produce the following rows:
      | id |
      | 1  |
"""

PROSE_THEN_SOURCE = """Feature: F

  @unit
  Scenario: Prose then not allowed in unit tier
    Given the following rows in "upstream_model":
      | id |
      | 1  |
    When the "downstream_model" model runs
    Then "downstream_model" should have 1 row
"""


def test_refuses_a_target_that_looks_like_production(tmp_path: Path):
    with pytest.raises(ProdSchemaGuardError):
        ModelUnitTestCompiler(project_dir=tmp_path, profiles_dir=tmp_path, target="prod")


def test_compile_error_propagates_without_touching_dbt_at_all(tmp_path: Path):
    # tmp_path is not a real dbt project -- if this reached dbtRunner it
    # would fail with a *different* error than UnitTestCompileError, so this
    # also proves compile_scenario runs before _ensure_project_prebuilt.
    compiler = ModelUnitTestCompiler(project_dir=tmp_path, profiles_dir=tmp_path)
    scenario = parse_feature_text(PROSE_THEN_SOURCE).scenarios[0]
    with pytest.raises(UnitTestCompileError):
        compiler.run(scenario)


def test_run_translates_a_passing_unit_test_to_all_passing_step_results(
    scratch_dbt_project_with_upstream: Path,
):
    compiler = ModelUnitTestCompiler(
        project_dir=scratch_dbt_project_with_upstream,
        profiles_dir=scratch_dbt_project_with_upstream / "profiles",
    )
    scenario = parse_feature_text(PASSING_SOURCE).scenarios[0]
    step_results = compiler.run(scenario)
    assert len(step_results) == 3  # Given, When, Then
    assert all(r.passed for r in step_results)


def test_run_translates_a_failing_unit_test_with_ansi_stripped_diff(
    scratch_dbt_project_with_upstream: Path,
):
    compiler = ModelUnitTestCompiler(
        project_dir=scratch_dbt_project_with_upstream,
        profiles_dir=scratch_dbt_project_with_upstream / "profiles",
    )
    scenario = parse_feature_text(FAILING_SOURCE).scenarios[0]
    step_results = compiler.run(scenario)
    assert step_results[0].passed is True  # Given
    assert step_results[1].passed is True  # When
    assert step_results[2].passed is False  # Then
    assert "\x1b[" not in step_results[2].error
    assert "ZZZ" in step_results[2].error


def test_run_tears_down_the_generated_yaml_file_on_pass_and_on_fail(
    scratch_dbt_project_with_upstream: Path,
):
    compiler = ModelUnitTestCompiler(
        project_dir=scratch_dbt_project_with_upstream,
        profiles_dir=scratch_dbt_project_with_upstream / "profiles",
    )
    for source in (PASSING_SOURCE, FAILING_SOURCE):
        scenario = parse_feature_text(source).scenarios[0]
        compiler.run(scenario)
        assert list((scratch_dbt_project_with_upstream / "models").glob("_specdbt_*.yml")) == []


def test_run_raises_dbt_invocation_error_when_the_model_does_not_exist(
    scratch_dbt_project_with_upstream: Path,
):
    compiler = ModelUnitTestCompiler(
        project_dir=scratch_dbt_project_with_upstream,
        profiles_dir=scratch_dbt_project_with_upstream / "profiles",
    )
    scenario = parse_feature_text(BAD_MODEL_SOURCE).scenarios[0]
    with pytest.raises(DbtInvocationError):
        compiler.run(scenario)
    assert list((scratch_dbt_project_with_upstream / "models").glob("_specdbt_*.yml")) == []


def test_run_works_across_multiple_calls_on_the_same_compiler_instance(
    scratch_dbt_project_with_upstream: Path,
):
    # exercises the prebuild-once-not-per-scenario path (spec §4.1 finding 6)
    compiler = ModelUnitTestCompiler(
        project_dir=scratch_dbt_project_with_upstream,
        profiles_dir=scratch_dbt_project_with_upstream / "profiles",
    )
    scenario = parse_feature_text(PASSING_SOURCE).scenarios[0]
    first = compiler.run(scenario)
    second = compiler.run(scenario)
    assert all(r.passed for r in first)
    assert all(r.passed for r in second)
