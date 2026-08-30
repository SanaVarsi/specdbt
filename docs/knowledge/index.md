---
okf_version: "0.2"
---

# specdbt Knowledge Bundle

Architecture reference for the specdbt codebase, in [Open Knowledge
Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
v0.2. Each linked file below is a concept document: a `type` in its
frontmatter, prose in its body, cross-links to related concepts.

* [Pipeline](pipeline.md) - end-to-end flow from `.feature` file to
  terminal report
* [Two-Tier Design](two-tier-design.md) - unit vs integration tier split,
  the core execution decision
* [Adapters](adapters.md) - `ExecutionAdapter` boundary and its
  implementations
* [dbt Integration](dbt-integration.md) - macro-tier adapter-dispatch
  plumbing
* [Native Unit Tests](native-unit-tests.md) - model unit-tier compiler
* [CLI](cli.md) - click entrypoint
* [AI Stubs](ai.md) - unbuilt Phase 3 package
* [Gherkin Style Guide](gherkin-style-guide.md) - rules for writing
  declarative, business-behavior-named scenarios
* [Databricks Validation Checklist](databricks-validation-checklist.md) -
  manual steps to validate the macro tier against a real Databricks
  workspace
