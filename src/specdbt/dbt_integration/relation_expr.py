"""Builds `api.Relation.create(...)` text consistently everywhere the macro
tier needs a real Relation object -- schema DDL (macro_file.py), fixture
CTAS targets (fixture_sql.py), and ref()/source() substitution
(ref_substitution.py). One shared builder means these three call sites can
never disagree about which catalog/schema/identifier they're addressing
(spec: macro-tier adapter-dispatch design, 2026-08-30)."""

from __future__ import annotations


def relation_expr(
    *, schema: str, identifier: str | None = None, database: str | None = None
) -> str:
    parts = []
    if database is not None:
        parts.append(f"database='{database}'")
    parts.append(f"schema='{schema}'")
    if identifier is not None:
        parts.append(f"identifier='{identifier}'")
    return f"api.Relation.create({', '.join(parts)})"
