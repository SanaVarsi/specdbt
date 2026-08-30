# specdbt Gherkin Style Guide

specdbt invents no Gherkin dialect. Every rule below is a constraint on how
you use features standard Gherkin already has, grounded directly in
Cucumber's own BDD guidance (`cucumber.io/docs/bdd`,
`cucumber.io/docs/bdd/better-gherkin`) — not a specdbt-specific convention.

## Write declarative scenarios, not imperative ones

A scenario states *what* should be true, not the steps a human would click
through to get there. This is the one property that makes a scenario both
good living documentation for a non-technical reader and good context for
an LLM to extend by analogy — not two separate goals.

**Imperative (avoid):**

```gherkin
Given I insert a row into "raw_customers" with id 1
And I run dbt on "stg_customers"
And I query "stg_customers"
Then the first row's customer_id column equals 1
```

**Declarative (required):**

```gherkin
Given the following rows in "raw_customers":
  | id | first_name |
  | 1  | Michael    |
When the "stg_customers" model runs
Then the "stg_customers" should produce the following rows:
  | customer_id | first_name |
  | 1           | Michael    |
```

The declarative version states the transformation's *contract* (rename
`id` to `customer_id`, pass `first_name` through) — it reads the same
whether a human, an LLM, or `specdbt docs` (a future command, not yet
built) is the audience.

## Name scenarios by business behavior, not mechanism

`Scenario: Uppercases status` describes what a person cares about.
`Scenario: Test case 3` or `Scenario: upper() macro call` does not — it
requires opening the scenario body to learn anything.

## Data tables are the default; doc strings are the escape hatch

The row-table `Given`/`Then` forms (`the following rows in "<x>":` /
`the "<x>" should produce the following rows:`) are how almost every
scenario in this project expresses fixtures and expectations — see every
example under `examples/`. Gherkin's doc-string syntax with a content-type
annotation (` ```markdown `, ` ```json `) is reserved for the rare case
where an expected payload is a large structured blob a data table would
make unreadable. No scenario in this project needs it yet — this section
exists so a future one that does knows the mechanism is sanctioned, not
invented ad hoc.

## Tag scenarios for what's actually true about them, not for routing tricks

`@unit` / `@integration` (spec §3) state which tier a scenario needs — use
them only when the resource-kind default (model → unit, macro →
integration) is wrong for a specific scenario, not as a habit. `@incremental_model`
(spec §4.1 finding 8) states a real fact about the model under test — it
belongs on every scenario for an incremental model, not just the ones that
happen to need `input: this`.
