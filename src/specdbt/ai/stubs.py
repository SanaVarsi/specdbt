"""Typed placeholders for a future AI layer. Nothing here executes; this
only fixes the package shape now so that layer is additive later, not a
restructure."""

from __future__ import annotations

_NOT_YET = "AI features ship in Phase 3 -- see the roadmap doc."


class LLMClient:
    """Placeholder for the provider-agnostic LLM client (Phase 3)."""

    def complete(self, prompt: str) -> str:
        raise NotImplementedError(_NOT_YET)


def generate_fixtures(model_sql: str, schema: dict[str, str], count: int = 3) -> list[dict]:
    """Fixture synthesis (Phase 3, 03-ai-integration-plan.md §1)."""
    raise NotImplementedError(_NOT_YET)


def scenario_from_text(description: str) -> str:
    """Natural-language -> Gherkin (Phase 3, 03-ai-integration-plan.md §2)."""
    raise NotImplementedError(_NOT_YET)


def explain_failure(fixture: dict, model_sql: str, diff: dict) -> str:
    """Failure triage (Phase 3, 03-ai-integration-plan.md §4)."""
    raise NotImplementedError(_NOT_YET)
