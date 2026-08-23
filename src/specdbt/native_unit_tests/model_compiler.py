"""Compiles a Gherkin Scenario (Given fixtures, incremental tag/step
wording, canonical row-table Then) into the pieces render_unit_test_yaml
needs (spec §4, §4.1, §6). Pure -- no dbt invocation, no file I/O; also
carries the original Step objects so the caller can echo real step text
back into StepResults, matching how the integration tier's report reads.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from specdbt.assertions import PRODUCES_ROWS_RE
from specdbt.parser import Scenario, Step
from specdbt.typing_utils import rows_from_data_table

_GIVEN_ROWS_RE = re.compile(r'the following rows in "([^"]+)":')
_GIVEN_ROWS_ALREADY_IN_RE = re.compile(r'the following rows already in "([^"]+)":')
_WHEN_MODEL_RE = re.compile(r'the "([^"]+)" model runs$')

TAG_INCREMENTAL_MODEL = "@incremental_model"


class UnitTestCompileError(ValueError):
    """Raised when a scenario resolved to the unit tier can't be compiled to
    a unit_tests: YAML entry -- names the fix, per spec §6."""


@dataclass
class CompiledUnitTest:
    model_name: str
    given: list[dict]
    expect_rows: list[dict]
    is_incremental: bool | None
    given_steps: list[Step] = field(default_factory=list)
    when_step: Step | None = None
    then_step: Step | None = None


def compile_scenario(scenario: Scenario) -> CompiledUnitTest:
    model_name: str | None = None
    given: list[dict] = []
    given_steps: list[Step] = []
    expect_rows: list[dict] | None = None
    has_already_in = False
    when_step: Step | None = None
    then_step: Step | None = None

    for step in scenario.steps:
        if step.type == "Context":
            given_steps.append(step)
            already_in_match = _GIVEN_ROWS_ALREADY_IN_RE.search(step.text)
            if already_in_match is not None:
                has_already_in = True
                if not step.table:
                    raise UnitTestCompileError(f"Given step has no data table: {step.text!r}")
                given.append({"input": "this", "rows": rows_from_data_table(step.table)})
                continue
            rows_match = _GIVEN_ROWS_RE.search(step.text)
            if rows_match is None:
                raise UnitTestCompileError(
                    "@unit scenario's Given step doesn't match a supported "
                    f"fixture pattern: {step.text!r}"
                )
            if not step.table:
                raise UnitTestCompileError(f"Given step has no data table: {step.text!r}")
            fixture_name = rows_match.group(1)
            given.append(
                {"input": f"ref('{fixture_name}')", "rows": rows_from_data_table(step.table)}
            )
        elif step.type == "Action":
            when_step = step
            model_match = _WHEN_MODEL_RE.search(step.text)
            if model_match is None:
                raise UnitTestCompileError(
                    "@unit scenario's When step must be 'the \"<model>\" model "
                    "runs' -- macro unit testing has no native dbt mechanism yet "
                    f"(dbt-core#10547); tag @integration instead. Got: {step.text!r}"
                )
            model_name = model_match.group(1)
        else:  # "Outcome"
            then_step = step
            then_match = PRODUCES_ROWS_RE.match(step.text)
            if then_match is None:
                raise UnitTestCompileError(
                    "@unit scenario's Then step must be the canonical "
                    '"...should produce the following rows:" form (spec §6) -- '
                    f"prose assertions have nothing to translate to in the "
                    f"unit tier. Got: {step.text!r}"
                )
            if not step.table:
                raise UnitTestCompileError(f"{step.text!r} requires a data table of expected rows")
            expect_rows = rows_from_data_table(step.table)

    if when_step is None or model_name is None:
        raise UnitTestCompileError(f'@unit scenario "{scenario.name}" has no When step')
    if then_step is None or expect_rows is None:
        raise UnitTestCompileError(
            f'@unit scenario "{scenario.name}" has no row-table Then step -- '
            "add one, or tag @integration explicitly (spec §6)"
        )

    is_incremental: bool | None = None
    if TAG_INCREMENTAL_MODEL in scenario.tags:
        is_incremental = has_already_in

    return CompiledUnitTest(
        model_name=model_name,
        given=given,
        expect_rows=expect_rows,
        is_incremental=is_incremental,
        given_steps=given_steps,
        when_step=when_step,
        then_step=then_step,
    )
