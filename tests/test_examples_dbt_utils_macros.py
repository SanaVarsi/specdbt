"""End-to-end: real dbt_utils macros against a real DuckDB target, run
through the actual CLI a user would run (spec §8, §12 DoD)."""

import subprocess
import sys
from pathlib import Path

EXAMPLE_PROJECT = Path(__file__).parent.parent / "examples" / "dbt_utils_macros"
# The venv's own `dbt` console script, resolved by sibling path rather than
# PATH lookup -- a bare "dbt" could silently pick up an unrelated system
# install; sys.executable's directory is where `uv sync` put this venv's own.
DBT_BIN = Path(sys.executable).parent / "dbt"


def test_dbt_utils_macro_examples_all_pass():
    if not (EXAMPLE_PROJECT / "dbt_packages").exists():
        subprocess.run(
            [str(DBT_BIN), "deps", "--profiles-dir", "profiles"],
            cwd=EXAMPLE_PROJECT,
            check=True,
            capture_output=True,
        )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "specdbt.cli",
            "run",
            str(EXAMPLE_PROJECT / "features"),
            "--engine",
            "dbt",
            "--project-dir",
            str(EXAMPLE_PROJECT),
            "--profiles-dir",
            str(EXAMPLE_PROJECT / "profiles"),
        ],
        capture_output=True,
        text=True,
        cwd=EXAMPLE_PROJECT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 scenario(s)" in result.stdout
    assert "0 failure(s)" in result.stdout
