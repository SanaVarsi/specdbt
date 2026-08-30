"""Fixture Builder: turns a Given step's data table into a typed Fixture."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from specdbt.parser import Step
from specdbt.typing_utils import rows_from_data_table

_GIVEN_ROWS_RE = re.compile(r'the following rows in "([^"]+)":')


@dataclass
class Fixture:
    name: str
    rows: list[dict] = field(default_factory=list)


class FixtureBuildError(ValueError):
    """Raised when a Given step's text/table can't be turned into a Fixture."""


def build_fixture(step: Step) -> Fixture:
    if step.type != "Context":
        raise FixtureBuildError(f"expected a Given step, got a {step.type} step: {step.text!r}")

    match = _GIVEN_ROWS_RE.search(step.text)
    if match is None:
        raise FixtureBuildError(
            f"Given step text does not match the supported fixture pattern: {step.text!r}"
        )
    if not step.table:
        raise FixtureBuildError(f"Given step has no data table: {step.text!r}")

    name = match.group(1)
    rows = rows_from_data_table(step.table)
    return Fixture(name=name, rows=rows)
