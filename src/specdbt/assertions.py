"""Then-step assertion library (Phase 0 subset — see spec §4)."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

import polars as pl

from specdbt.adapters.base import ExecutionResult
from specdbt.typing_utils import coerce_scalar, rows_from_data_table


class AssertionFailure(AssertionError):
    def __init__(self, message: str, expected: object = None, actual: object = None) -> None:
        super().__init__(message)
        self.expected = expected
        self.actual = actual


class UnrecognizedStepError(ValueError):
    """Raised when a Then/And/But step's text matches none of the known patterns."""


PRODUCES_ROWS_RE = re.compile(r'the "(.+)" should produce the following rows:$')
_ROW_COUNT_RE = re.compile(r'^"([^"]+)" should have (\d+) rows?$')
_NOT_NULL_RE = re.compile(r'^column "([^"]+)" in "([^"]+)" should not contain nulls$')
_UNIQUE_RE = re.compile(r'^column "([^"]+)" in "([^"]+)" should be unique$')
_ROW_FIELD_RE = re.compile(r'^the row for (\w+) "([^"]+)" should have (\w+) (.+)$')


@dataclass
class ThenContext:
    """What a Then/And/But step needs: every named result produced so far in the
    scenario, and the most recently produced one (for steps that don't name a
    model explicitly, like "the row for X should have Y")."""

    results: dict[str, ExecutionResult]
    last_model: str | None


def evaluate_then_step(text: str, ctx: ThenContext, table: list[list[str]] | None = None) -> None:
    """Raise AssertionFailure if the expectation doesn't hold, or
    UnrecognizedStepError if the text matches no known pattern. None on
    success. `table` is the step's data table, if it has one -- only the
    row-table form (the canonical Then, spec §6) uses it."""
    if (m := PRODUCES_ROWS_RE.match(text)) is not None:
        name = m.group(1)
        if not table:
            raise AssertionFailure(f"{text!r} requires a data table of expected rows")
        result = _lookup(ctx, name)
        header = table[0]
        expected_rows = rows_from_data_table(table)
        projected_actual_rows = [
            {column: row.get(column) for column in header} for row in result.rows
        ]
        expected_counts = Counter(tuple(row[c] for c in header) for row in expected_rows)
        actual_counts = Counter(tuple(row[c] for c in header) for row in projected_actual_rows)
        if actual_counts != expected_counts:
            expected_df = pl.DataFrame(expected_rows) if expected_rows else pl.DataFrame()
            actual_df = (
                pl.DataFrame(projected_actual_rows) if projected_actual_rows else pl.DataFrame()
            )
            raise AssertionFailure(
                f'"{name}" produced different rows than expected (only columns '
                f"{header} are compared; row order doesn't matter, row count "
                f"does):\n"
                f"--- expected ---\n{expected_df}\n"
                f"--- actual (projected) ---\n{actual_df}",
                expected=expected_rows,
                actual=projected_actual_rows,
            )
        return

    if (m := _ROW_COUNT_RE.match(text)) is not None:
        model_name, expected_count = m.group(1), int(m.group(2))
        result = _lookup(ctx, model_name)
        if result.row_count != expected_count:
            raise AssertionFailure(
                f'expected "{model_name}" to have {expected_count} row(s), got {result.row_count}',
                expected=expected_count,
                actual=result.row_count,
            )
        return

    if (m := _NOT_NULL_RE.match(text)) is not None:
        column, model_name = m.group(1), m.group(2)
        result = _lookup(ctx, model_name)
        nulls = [row for row in result.rows if row.get(column) is None]
        if nulls:
            raise AssertionFailure(
                f'expected column "{column}" in "{model_name}" to contain no nulls, '
                f"found {len(nulls)}",
                expected="no nulls",
                actual=f"{len(nulls)} null row(s)",
            )
        return

    if (m := _UNIQUE_RE.match(text)) is not None:
        column, model_name = m.group(1), m.group(2)
        result = _lookup(ctx, model_name)
        values = [row.get(column) for row in result.rows]
        duplicates = sorted({v for v in values if values.count(v) > 1}, key=str)
        if duplicates:
            raise AssertionFailure(
                f'expected column "{column}" in "{model_name}" to be unique, '
                f"found duplicate(s) {duplicates}",
                expected="unique values",
                actual=f"duplicates: {duplicates}",
            )
        return

    if (m := _ROW_FIELD_RE.match(text)) is not None:
        key_col, key_val_raw, field_name, raw_value = m.groups()
        if ctx.last_model is None:
            raise AssertionFailure(f"no model has run yet to check a row against: {text!r}")
        result = _lookup(ctx, ctx.last_model)
        key_val = coerce_scalar(key_val_raw)
        matches = [row for row in result.rows if row.get(key_col) == key_val]
        if not matches:
            raise AssertionFailure(
                f'no row found where {key_col} == {key_val_raw!r} in "{ctx.last_model}"',
                expected=f"a row with {key_col}={key_val_raw!r}",
                actual="no matching row",
            )
        expected_value = coerce_scalar(raw_value.strip('"'))
        actual_value = matches[0].get(field_name)
        if actual_value != expected_value:
            raise AssertionFailure(
                f"expected {field_name} {expected_value!r} for row {key_col}={key_val_raw!r}, "
                f"got {actual_value!r}",
                expected=expected_value,
                actual=actual_value,
            )
        return

    raise UnrecognizedStepError(f"no assertion pattern matches: {text!r}")


def _lookup(ctx: ThenContext, model_name: str) -> ExecutionResult:
    try:
        return ctx.results[model_name]
    except KeyError:
        raise AssertionFailure(f'model "{model_name}" has not run yet in this scenario') from None
