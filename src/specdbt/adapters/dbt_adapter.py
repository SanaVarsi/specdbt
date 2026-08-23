"""Real execution against whatever dbt target a project's profile points at,
via dbtRunner -- the only concrete ExecutionAdapter that computes real
results instead of returning canned ones (spec §3, §5)."""

from __future__ import annotations

from pathlib import Path

from dbt.cli.main import dbtRunner

from specdbt.adapters.base import ExecutionAdapter, ExecutionResult
from specdbt.fixtures import Fixture


class DbtInvocationError(RuntimeError):
    """Raised when a dbtRunner.invoke() call fails."""


class ProdSchemaGuardError(RuntimeError):
    """Raised when the configured target name looks like production and
    allow_any_schema was not passed."""


class ModelIntegrationTierNotImplementedError(NotImplementedError):
    """Raised by run_model -- see spec §10. The macro-file substitution
    mechanism only works because a macro call's ref()/source() arguments
    are text specdbt's own call site controls. A model's ref()s are inside
    its own SQL file, which this mechanism never touches -- running it for
    real would use whatever real state those refs already resolve to, not
    the scenario's fixtures, silently producing wrong results."""


class DbtExecutionAdapter(ExecutionAdapter):
    def __init__(
        self,
        project_dir: Path,
        profiles_dir: Path,
        *,
        target: str | None = None,
        allow_any_schema: bool = False,
        keep_schema: bool = False,
    ) -> None:
        if target and "prod" in target.lower() and not allow_any_schema:
            raise ProdSchemaGuardError(
                f"target {target!r} looks like production -- refusing to run. "
                "Pass allow_any_schema=True (CLI: --allow-any-schema) if this "
                "is really what you want."
            )
        self._project_dir = Path(project_dir)
        self._profiles_dir = Path(profiles_dir)
        self._target = target
        self._keep_schema = keep_schema
        self._runner = dbtRunner()

    def run_model(self, model_name: str, fixtures: list[Fixture]) -> ExecutionResult:
        raise ModelIntegrationTierNotImplementedError(
            f"DbtExecutionAdapter.run_model({model_name!r}) is an extension "
            "point, not implemented -- see spec §2/§3/§10. Model testing "
            "today goes through FakeAdapter, or (a future plan) the unit tier."
        )

    def run_macro(self, macro_call: str, fixtures: list[Fixture]) -> ExecutionResult:
        raise NotImplementedError("implemented in Task 7")

    def _invoke(self, args: list[str]):
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
        result = self._runner.invoke(full_args)
        if not result.success:
            raise DbtInvocationError(f"dbt {args[0]} failed: {result.exception}")
        return result
