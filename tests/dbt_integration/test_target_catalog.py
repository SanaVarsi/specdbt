from pathlib import Path

from specdbt.dbt_integration.target_catalog import resolve_target_catalog


def _write_project(tmp_path: Path, profile_body: str) -> Path:
    project_dir = tmp_path / "proj"
    (project_dir / "profiles").mkdir(parents=True)
    (project_dir / "dbt_project.yml").write_text(
        'name: scratch\nversion: "1.0.0"\nconfig-version: 2\nprofile: scratch\n'
    )
    (project_dir / "profiles" / "profiles.yml").write_text(profile_body)
    return project_dir


def test_no_catalog_or_database_key_resolves_to_none(tmp_path: Path):
    project_dir = _write_project(
        tmp_path,
        "scratch:\n  target: dev\n  outputs:\n    dev:\n      type: duckdb\n"
        '      path: "s.duckdb"\n      schema: main\n',
    )
    assert resolve_target_catalog(project_dir, project_dir / "profiles", None) is None


def test_catalog_key_is_used_when_present(tmp_path: Path):
    project_dir = _write_project(
        tmp_path,
        "scratch:\n  target: dev\n  outputs:\n    dev:\n      type: databricks\n"
        "      catalog: my_catalog\n      schema: main\n",
    )
    assert resolve_target_catalog(project_dir, project_dir / "profiles", None) == "my_catalog"


def test_database_key_used_when_catalog_key_absent(tmp_path: Path):
    project_dir = _write_project(
        tmp_path,
        "scratch:\n  target: dev\n  outputs:\n    dev:\n      type: postgres\n"
        "      database: specdbt_test\n      schema: main\n",
    )
    assert resolve_target_catalog(project_dir, project_dir / "profiles", None) == "specdbt_test"


def test_env_var_in_catalog_is_rendered(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SPECDBT_TEST_CATALOG", "env_catalog")
    project_dir = _write_project(
        tmp_path,
        "scratch:\n  target: dev\n  outputs:\n    dev:\n      type: databricks\n"
        "      catalog: \"{{ env_var('SPECDBT_TEST_CATALOG') }}\"\n      schema: main\n",
    )
    assert resolve_target_catalog(project_dir, project_dir / "profiles", None) == "env_catalog"


def test_target_override_selects_the_right_output(tmp_path: Path):
    project_dir = _write_project(
        tmp_path,
        "scratch:\n  target: dev\n  outputs:\n    dev:\n      type: duckdb\n"
        '      path: "s.duckdb"\n      schema: main\n'
        "    ci:\n      type: databricks\n      catalog: ci_catalog\n      schema: main\n",
    )
    assert resolve_target_catalog(project_dir, project_dir / "profiles", None) is None
    assert resolve_target_catalog(project_dir, project_dir / "profiles", "ci") == "ci_catalog"
