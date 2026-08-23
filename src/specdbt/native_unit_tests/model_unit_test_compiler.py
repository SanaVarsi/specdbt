"""Real unit-tier orchestration for models: compiles a Scenario to a
generated unit_tests: YAML file, runs it for real via dbtRunner, and
translates dbt's own pass/fail + diff into specdbt's StepResult format
(spec §4, §4.1). The only NativeTestCompiler this plan registers -- the
macro slot stays unregistered (spec §5.4, dbt-core#10547).
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import yaml as _yaml
from dbt.cli.main import dbtRunner

from specdbt.adapters.prod_guard import guard_against_prod_target
from specdbt.native_unit_tests.compiler import NativeTestCompiler
from specdbt.native_unit_tests.model_compiler import compile_scenario
from specdbt.native_unit_tests.yaml_file import (
    delete_unit_test_yaml,
    render_unit_test_yaml,
    unit_test_name,
    write_unit_test_yaml,
)
from specdbt.parser import Scenario
from specdbt.reporter import StepResult

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class DbtInvocationError(RuntimeError):
    """Raised when a dbtRunner.invoke() call itself fails to run -- a
    seed/run prebuild step failing outright, or a test invocation whose
    result.result is None (a genuine parse/compile error, spec §4.1
    finding 2) -- never for a unit test that ran and legitimately failed;
    that case is translated into a failed StepResult instead."""


class ModelUnitTestCompiler(NativeTestCompiler):
    def __init__(
        self,
        project_dir: Path,
        profiles_dir: Path,
        *,
        target: str | None = None,
        allow_any_schema: bool = False,
    ) -> None:
        guard_against_prod_target(target, allow_any_schema)
        self._project_dir = Path(project_dir)
        self._profiles_dir = Path(profiles_dir)
        self._target = target
        self._runner = dbtRunner()
        self._prebuilt = False

    def run(self, scenario: Scenario) -> list[StepResult]:
        compiled = compile_scenario(scenario)
        self._ensure_project_prebuilt()

        run_id = uuid.uuid4().hex
        project_name = self._project_name()
        yaml_text = render_unit_test_yaml(
            run_id=run_id,
            model_name=compiled.model_name,
            given=compiled.given,
            expect_rows=compiled.expect_rows,
            is_incremental=compiled.is_incremental,
        )
        yaml_path = write_unit_test_yaml(self._project_dir, run_id, yaml_text)
        try:
            selector = f"unit_test:{project_name}.{unit_test_name(run_id)}"
            result = self._invoke_test(["test", "--select", selector])
            test_result = result.result.results[0]
            passed = test_result.status == "pass"
            message = _ANSI_RE.sub("", test_result.message or "") if not passed else None

            given_results = [
                StepResult(s.keyword, s.text, passed=True) for s in compiled.given_steps
            ]
            when_result = StepResult(
                compiled.when_step.keyword, compiled.when_step.text, passed=True
            )
            then_result = StepResult(
                compiled.then_step.keyword, compiled.then_step.text, passed=passed, error=message
            )
            return [*given_results, when_result, then_result]
        finally:
            delete_unit_test_yaml(yaml_path)

    def _ensure_project_prebuilt(self) -> None:
        """One dbt seed + dbt run for the whole project, once per compiler
        instance -- not per scenario. Necessary and sufficient for every
        given: input: ref()/source()/this target to be a real,
        introspectable relation before any unit test runs (spec §4.1
        findings 6, 8)."""
        if self._prebuilt:
            return
        self._invoke_must_succeed(["seed"])
        self._invoke_must_succeed(["run"])
        self._prebuilt = True

    def _project_name(self) -> str:
        project_yml = self._project_dir / "dbt_project.yml"
        return _yaml.safe_load(project_yml.read_text())["name"]

    def _invoke_must_succeed(self, args: list[str]):
        result = self._raw_invoke(args)
        if not result.success:
            raise DbtInvocationError(f"dbt {args[0]} failed: {result.exception}")
        return result

    def _invoke_test(self, args: list[str]):
        """Unlike _invoke_must_succeed, result.success == False is the
        NORMAL outcome of a legitimately failing unit test (spec §4.1
        finding 2) -- only result.result is None (dbt couldn't even run: a
        parse/compile error) is a real invocation failure here."""
        result = self._raw_invoke(args)
        if result.result is None:
            raise DbtInvocationError(f"dbt {args[0]} failed to run: {result.exception}")
        return result

    def _raw_invoke(self, args: list[str]):
        full_args = [
            *args,
            "--project-dir",
            str(self._project_dir),
            "--profiles-dir",
            str(self._profiles_dir),
            "--quiet",
            "--no-send-anonymous-usage-stats",
        ]
        if self._target:
            full_args += ["--target", self._target]
        return self._runner.invoke(full_args)
