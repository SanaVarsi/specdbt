"""Renders a compiled unit test as a dbt-native `unit_tests:` YAML entry,
and writes/deletes the generated file specdbt writes into the target
project (spec §4, §4.1) -- mirrors dbt_integration/macro_file.py's
render/write/delete shape for the macro tier.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def unit_test_name(run_id: str) -> str:
    return f"_specdbt_{run_id}"


def render_unit_test_yaml(
    *,
    run_id: str,
    model_name: str,
    given: list[dict],
    expect_rows: list[dict],
    is_incremental: bool | None,
) -> str:
    """`given` is a list of {"input": <"ref('x')" | "source('a','b')" |
    "this">, "rows": list[dict]} dicts, already compiled by
    native_unit_tests.model_compiler.compile_scenario (Task 6).
    `is_incremental`: None omits the overrides block entirely (models that
    don't call is_incremental()); True/False emits an explicit
    overrides: macros: is_incremental: <bool> (spec §4.1 finding 8 -- dbt
    requires this be explicit for any unit test on a model that does)."""
    entry: dict = {
        "name": unit_test_name(run_id),
        "model": model_name,
        "given": [{"input": g["input"], "rows": g["rows"]} for g in given],
        "expect": {"rows": expect_rows},
    }
    if is_incremental is not None:
        entry["overrides"] = {"macros": {"is_incremental": is_incremental}}
    return yaml.safe_dump({"unit_tests": [entry]}, sort_keys=False)


def write_unit_test_yaml(project_dir: Path, run_id: str, content: str) -> Path:
    path = Path(project_dir) / "models" / f"{unit_test_name(run_id)}.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def delete_unit_test_yaml(path: Path) -> None:
    Path(path).unlink(missing_ok=True)
