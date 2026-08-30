"""Shared prod-schema heuristic guard (spec §5.3) -- used by every real-
execution path that touches a dbt target: DbtExecutionAdapter (macro/model
integration tier, ephemeral) and ModelUnitTestCompiler (model unit tier --
its prebuild step, spec §4.1 finding 6, writes real tables into the
project's actually-configured schema, not an ephemeral one, so it needs the
same guard).
"""

from __future__ import annotations


class ProdSchemaGuardError(RuntimeError):
    """Raised when the configured target name looks like production and
    allow_any_schema was not passed."""


def guard_against_prod_target(target: str | None, allow_any_schema: bool) -> None:
    if target and "prod" in target.lower() and not allow_any_schema:
        raise ProdSchemaGuardError(
            f"target {target!r} looks like production -- refusing to run. "
            "Pass allow_any_schema=True (CLI: --allow-any-schema) if this "
            "is really what you want."
        )
