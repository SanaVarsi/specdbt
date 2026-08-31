"""End-to-end: real jaffle_shop models and dbt_utils macros against a real
DuckDB target, run through the actual CLI. Covers both tiers -- models
default to the unit tier, macros to the integration tier."""

import shutil
import subprocess
import sys
from pathlib import Path

EXAMPLE_PROJECT = Path(__file__).parent.parent / "examples" / "jaffle_shop"
# Resolved by sibling path, not PATH lookup, so this is the venv's own dbt
# and not an unrelated system install.
DBT_BIN = Path(sys.executable).parent / "dbt"


def test_jaffle_shop_examples_all_pass():
    # dbt's partial-parse cache records seed paths relative to the cwd it
    # was built from; a stale cache from a different cwd causes spurious
    # "seed file not found" errors, so clear it before running.
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
