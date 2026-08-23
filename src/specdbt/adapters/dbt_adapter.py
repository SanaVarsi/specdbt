"""Real execution against whatever dbt target a project's profile points at,
via dbtRunner -- the only concrete ExecutionAdapter that computes real
results instead of returning canned ones (spec §3, §5)."""

from __future__ import annotations

import uuid
from pathlib import Path

from dbt.cli.main import dbtRunner

from specdbt.adapters.base import ExecutionAdapter, ExecutionResult
from specdbt.adapters.prod_guard import (  # noqa: F401 -- re-exported for tests/test_dbt_adapter.py
    ProdSchemaGuardError,
    guard_against_prod_target,
)
from specdbt.dbt_integration.fixture_sql import render_fixture_ctas
from specdbt.dbt_integration.macro_file import (
    delete_macro_file,
    render_macro_file,
    setup_macro_name,
    teardown_macro_name,
    write_macro_file,
)
from specdbt.dbt_integration.ref_substitution import substitute_fixture_refs
from specdbt.fixtures import Fixture


class DbtInvocationError(RuntimeError):
    """Raised when a dbtRunner.invoke() call fails."""


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
        guard_against_prod_target(target, allow_any_schema)
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
        run_id = uuid.uuid4().hex
        schema = f"specdbt_{run_id}"
        fixture_names = {fixture.name for fixture in fixtures}
        substituted_call = substitute_fixture_refs(macro_call, schema, fixture_names)
        fixture_ctas = [render_fixture_ctas(schema, fixture) for fixture in fixtures]
        macro_text = render_macro_file(run_id, schema, fixture_ctas)
        macro_path = write_macro_file(self._project_dir, run_id, macro_text)

        try:
            self._invoke(["run-operation", setup_macro_name(run_id)])
            show_result = self._invoke(
                ["show", "--inline", substituted_call, "--output", "json", "--limit", "-1"]
            )
            agate_table = show_result.result.results[0].agate_table
            rows = [
                dict(zip(agate_table.column_names, row, strict=True)) for row in agate_table.rows
            ]
            return ExecutionResult.of(rows)
        finally:
            if not self._keep_schema:
                self._invoke(["run-operation", teardown_macro_name(run_id)])
                delete_macro_file(macro_path)

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
