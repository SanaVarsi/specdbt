---
name: specdbt
description: Load specdbt's OKF architecture knowledge bundle (docs/knowledge/) as context before answering questions about this repo's design, then offer to refresh any doc that looks stale against current source.
---

# specdbt Knowledge Bundle

This repo's architecture reference lives in `docs/knowledge/`, an [Open
Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
v0.2 bundle. Use it instead of a fresh grep/read of `src/` when answering
questions about specdbt's design.

## Steps

1. Read `docs/knowledge/index.md`.
2. Read every concept doc it links to (`pipeline.md`,
   `two-tier-design.md`, `adapters.md`, `dbt-integration.md`,
   `native-unit-tests.md`, `cli.md`, `ai.md`).
3. Answer the user's question grounded in that bundle. If something the
   user asks about isn't covered, say so rather than guessing, and fall
   back to reading the relevant source under `src/specdbt/`.
4. Before finishing, check whether anything you read in `src/` while
   answering contradicts a concept doc. If so, tell the user which doc
   looks stale and offer to update it — don't rewrite it automatically.
