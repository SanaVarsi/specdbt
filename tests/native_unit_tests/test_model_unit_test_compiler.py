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
    assert step_results[2].error is not None
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


def test_run_raises_dbt_invocation_error_when_prebuild_fails(
    scratch_dbt_project_with_upstream: Path,
):
    (scratch_dbt_project_with_upstream / "models" / "upstream_model.sql").write_text(
        "select * from no_such_table\n"
    )
    compiler = ModelUnitTestCompiler(
        project_dir=scratch_dbt_project_with_upstream,
        profiles_dir=scratch_dbt_project_with_upstream / "profiles",
    )
    scenario = parse_feature_text(PASSING_SOURCE).scenarios[0]
    with pytest.raises(DbtInvocationError):
        compiler.run(scenario)


def test_run_resolves_model_paths_dir_from_dbt_project_yml(
    scratch_dbt_project_with_upstream_custom_model_paths: Path,
):
    # final review finding 1, part 1: a project with a non-default
    # model-paths (here "transform") must still have the generated
    # unit-test YAML land where dbt actually parses it -- previously
    # hardcoded "models" meant the unit_test: selector matched nothing and
    # result.result.results[0] raised IndexError instead of a real result.
    compiler = ModelUnitTestCompiler(
        project_dir=scratch_dbt_project_with_upstream_custom_model_paths,
        profiles_dir=scratch_dbt_project_with_upstream_custom_model_paths / "profiles",
    )
    scenario = parse_feature_text(PASSING_SOURCE).scenarios[0]
    step_results = compiler.run(scenario)
    assert len(step_results) == 3
    assert all(r.passed for r in step_results)
    transform_dir = scratch_dbt_project_with_upstream_custom_model_paths / "transform"
    assert list(transform_dir.glob("_specdbt_*.yml")) == []


def test_run_raises_dbt_invocation_error_not_index_error_on_empty_results(
    scratch_dbt_project_with_upstream: Path, monkeypatch
):
    # final review finding 1, part 2: guards result.result.results[0]
    # against an empty list. Forced independently of part 1's model-paths
    # fix by making the selector's project name wrong, so
    # `unit_test:<project>.<name>` matches zero unit test nodes even
    # though the generated YAML is written to the correct directory.
    compiler = ModelUnitTestCompiler(
        project_dir=scratch_dbt_project_with_upstream,
        profiles_dir=scratch_dbt_project_with_upstream / "profiles",
    )
    monkeypatch.setattr(compiler, "_project_name", lambda: "not_the_real_project_name")
    scenario = parse_feature_text(PASSING_SOURCE).scenarios[0]
    with pytest.raises(DbtInvocationError, match="matched no unit test node"):
        compiler.run(scenario)


def test_run_raises_informative_message_when_prebuild_node_fails(
    scratch_dbt_project_with_upstream: Path,
):
    # final review finding 3: a node-level failure during the prebuild
    # seed/run step must not surface as the content-free "dbt run failed:
    # None" (result.exception is None here -- the invocation itself
    # succeeded, a node inside it failed).
    (scratch_dbt_project_with_upstream / "models" / "upstream_model.sql").write_text(
        "select * from no_such_table\n"
    )
    compiler = ModelUnitTestCompiler(
        project_dir=scratch_dbt_project_with_upstream,
        profiles_dir=scratch_dbt_project_with_upstream / "profiles",
    )
    scenario = parse_feature_text(PASSING_SOURCE).scenarios[0]
    with pytest.raises(DbtInvocationError) as exc_info:
        compiler.run(scenario)
    message = str(exc_info.value)
    assert message != "dbt run failed: None"
    assert "upstream_model" in message


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
