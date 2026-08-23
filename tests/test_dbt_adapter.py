from pathlib import Path

import pytest

from specdbt.adapters.dbt_adapter import (
    DbtExecutionAdapter,
    ModelIntegrationTierNotImplementedError,
    ProdSchemaGuardError,
)


def test_refuses_a_target_that_looks_like_production(tmp_path: Path):
    with pytest.raises(ProdSchemaGuardError):
        DbtExecutionAdapter(project_dir=tmp_path, profiles_dir=tmp_path, target="prod")


def test_allow_any_schema_overrides_the_guard(tmp_path: Path):
    adapter = DbtExecutionAdapter(
        project_dir=tmp_path, profiles_dir=tmp_path, target="prod", allow_any_schema=True
    )
    assert adapter is not None


def test_no_target_does_not_trigger_the_guard(tmp_path: Path):
    adapter = DbtExecutionAdapter(project_dir=tmp_path, profiles_dir=tmp_path)
    assert adapter is not None


def test_run_model_raises_not_implemented(scratch_dbt_project: Path):
    adapter = DbtExecutionAdapter(
        project_dir=scratch_dbt_project, profiles_dir=scratch_dbt_project / "profiles"
    )
    with pytest.raises(ModelIntegrationTierNotImplementedError):
        adapter.run_model("placeholder", [])
