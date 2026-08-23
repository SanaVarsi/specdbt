"""Shared scalar-value coercion for Gherkin cell/literal text -> Python types."""

from __future__ import annotations

import re

Scalar = bool | int | float | str

# Deliberately stricter than int()/float(): no leading zeros (so identifier-shaped
# values like "007" stay strings, not 7) and no scientific notation (so "1e5"
# isn't silently read as a number).
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
