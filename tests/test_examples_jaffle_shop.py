"""End-to-end: real jaffle_shop models against a real DuckDB target, run
through the actual CLI a user would run (spec §8, §12 DoD)."""

import subprocess
import sys
from pathlib import Path

EXAMPLE_PROJECT = Path(__file__).parent.parent / "examples" / "jaffle_shop"


def test_jaffle_shop_unit_examples_all_pass():
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
    assert "4 scenario(s)" in result.stdout
    assert "0 failure(s)" in result.stdout
