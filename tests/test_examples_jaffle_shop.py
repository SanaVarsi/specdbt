"""End-to-end: real jaffle_shop models and dbt_utils macros against a real
DuckDB target, run through the actual CLI a user would run (spec §8, §12
DoD). One project covers both tiers -- models default to the unit tier,
macros to the integration tier (spec §3)."""

import shutil
import subprocess
import sys
from pathlib import Path

EXAMPLE_PROJECT = Path(__file__).parent.parent / "examples" / "jaffle_shop"
# The venv's own `dbt` console script, resolved by sibling path rather than
# PATH lookup -- a bare "dbt" could silently pick up an unrelated system
# install; sys.executable's directory is where `uv sync` put this venv's own.
DBT_BIN = Path(sys.executable).parent / "dbt"


def test_jaffle_shop_examples_all_pass():
    # dbt's partial-parse cache under target/ records seed file paths
    # relative to the cwd it was built from. A prior manual run of this
    # same project from a different cwd (e.g. the repo root, as the
    # README's example does) leaves a cache dbt will trust without
    # re-resolving -- producing spurious "seed file not found" errors here.
    # This test always runs from EXAMPLE_PROJECT, so any stale cache from a
    # different cwd is invalid; clear it rather than risk reusing it.
    shutil.rmtree(EXAMPLE_PROJECT / "target", ignore_errors=True)

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
    assert "15 scenario(s)" in result.stdout
    assert "0 failure(s)" in result.stdout
