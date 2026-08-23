"""Shared scalar-value coercion for Gherkin cell/literal text -> Python types."""

from __future__ import annotations

Scalar = bool | int | float | str


def coerce_scalar(text: str) -> Scalar:
    """Best-effort coercion of a Gherkin cell or literal string to bool, int,
    float, or (falling through) str. Order matters: bool checked before int/float
    since Python's int()/float() don't accept "true"/"false"."""
    if text in ("true", "True"):
        return True
    if text in ("false", "False"):
        return False
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text
