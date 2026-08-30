---
type: Module
title: ai/ — Unbuilt Phase 3 Stubs
description: Placeholder AI-assist package; every function raises NotImplementedError. Not dead code — a planned phase.
tags: [module, ai, unbuilt]
---

# ai/ — Unbuilt Phase 3 Stubs

`ai/stubs.py` defines the intended future surface, all raising
`NotImplementedError`:

- `LLMClient.complete(prompt) -> str`
- `generate_fixtures(model_sql, schema, count=3) -> list[dict]`
- `scenario_from_text(description) -> str`
- `explain_failure(fixture, model_sql, diff) -> str`

This is a deliberate placeholder for a planned phase, not dead code —
don't delete it as unused.
