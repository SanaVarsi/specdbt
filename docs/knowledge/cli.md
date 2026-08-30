---
type: Module
title: cli.py — Command-Line Entrypoint
description: The click-based CLI surface that drives runner.py.
tags: [module, cli]
---

# cli.py — Command-Line Entrypoint

Click-based entrypoint, `cli()` group, with subcommands:

- `init(directory)` — scaffolds a new specdbt project layout.
- `run(...)` — the main command; `--engine fake|dbt` selects between
  `FakeAdapter` (loading canned results via `_load_canned_results(path)`,
  which reads a co-located `.canned.py`'s `CANNED_RESULTS` dict — see
  [Adapters](adapters.md)) and the real `DbtExecutionAdapter`. Calls into
  `runner.py` (see [Pipeline](pipeline.md)) to actually execute scenarios.
- `generate(from_model, fixtures_flag)` and `compile_(target, to_format)`
  — stubbed, not yet implemented.
