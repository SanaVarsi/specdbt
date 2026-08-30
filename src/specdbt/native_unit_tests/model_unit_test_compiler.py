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
        # compile_scenario raises before returning if either is None (see
        # its own checks) -- asserted here so the type checker can narrow
        # Step | None the same way that invariant already guarantees.
        assert compiled.when_step is not None
        assert compiled.then_step is not None
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
        yaml_path = write_unit_test_yaml(
            self._project_dir, run_id, yaml_text, model_paths_dir=self._model_paths_dir()
        )
        try:
            selector = f"unit_test:{project_name}.{unit_test_name(run_id)}"
            result = self._invoke_test(["test", "--select", selector])
            if not result.result.results:
                raise DbtInvocationError(
                    f"dbt test --select {selector!r} matched no unit test node -- "
                    "check model-paths in dbt_project.yml"
                )
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

    def _model_paths_dir(self) -> str:
        """dbt only parses YAML placed under model-paths (default
        ["models"]) -- the generated unit-test YAML must land there or dbt
        silently never sees it (spec §4.1, final review finding 1)."""
        project_yml = self._project_dir / "dbt_project.yml"
        config = _yaml.safe_load(project_yml.read_text())
        model_paths = config.get("model-paths") or ["models"]
        return model_paths[0]

    def _invoke_must_succeed(self, args: list[str]):
        result = self._raw_invoke(args)
        if not result.success:
            raise DbtInvocationError(f"dbt {args[0]} failed: {self._failure_detail(result)}")
        return result

    def _failure_detail(self, result) -> str:
        """Best-effort extraction of node-level failure info (each failing
        seed/run node's name + message) for a more informative diagnostic
        than the bare result.exception, which is None whenever the
        invocation itself ran fine but a node inside it failed (final
        review finding 3). Falls back to result.exception for genuine
        invocation-level failures, where result.result is None. Defensive:
        never lets a shape surprise here raise past this method."""
        if result.result is not None:
            try:
                details = []
                ok_statuses = {"success", "pass", "skipped", "no-op", "reused"}
                for node_result in result.result.results:
                    status = str(getattr(node_result, "status", ""))
                    if status and status not in ok_statuses:
                        node = getattr(node_result, "node", None)
                        name = getattr(node, "name", None) or "?"
                        message = getattr(node_result, "message", None) or "(no message)"
                        details.append(f"{name}: {message}")
                if details:
                    return "; ".join(details)
            except Exception:
                pass
        return str(result.exception)

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
