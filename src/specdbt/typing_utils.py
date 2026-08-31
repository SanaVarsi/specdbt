"""Shared scalar-value coercion for Gherkin cell/literal text -> Python types."""

from __future__ import annotations

import re

Scalar = bool | int | float | str

# Stricter than int()/float(): no leading zeros ("007" stays a string) and
# no scientific notation ("1e5" stays a string).
_INT_RE = re.compile(r"^-?(0|[1-9]\d*)$")
_FLOAT_RE = re.compile(r"^-?(0|[1-9]\d*)\.\d+$")


def coerce_scalar(text: str) -> Scalar | None:
    """Best-effort coercion of a Gherkin cell or literal string to None, bool,
    int, float, or (falling through) str.

    "NULL" is the explicit null literal (matches how dbt's own native
    `unit_tests:` fixtures spell null) -- an empty cell is a genuine empty
    string, not null; the two are not interchangeable.
    """
    if text == "NULL":
        return None
    if text in ("true", "True"):
        return True
    if text in ("false", "False"):
        return False
    if _INT_RE.match(text):
        return int(text)
    if _FLOAT_RE.match(text):
        return float(text)
    return text


def rows_from_data_table(table: list[list[str]]) -> list[dict]:
    """Turn a Gherkin data table (header row + data rows, both raw strings)
    into a list of dicts with coerced scalar values -- shared by every step
    kind that reads a data table: Given fixtures (fixtures.py), the
    integration tier's row-table Then (assertions.py), and the unit tier's
    compiler (native_unit_tests/model_compiler.py, Task 6). Caller must
    ensure table is non-empty."""
    header, *data_rows = table
    return [
        {column: coerce_scalar(value) for column, value in zip(header, row, strict=True)}
        for row in data_rows
    ]
