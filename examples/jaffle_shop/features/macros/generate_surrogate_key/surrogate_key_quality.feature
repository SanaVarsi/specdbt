Feature: generate_surrogate_key output satisfies row-count and uniqueness expectations

  Same macro as generate_surrogate_key.feature, checked here with
  assertion forms other than the canonical row table — row count and
  column uniqueness, the same properties a schema.yml `unique` test
  states about a real column.

  Scenario: Hashing N orders produces exactly N keys
    Given the following rows in "orders":
      | order_id | status    |
      | 1        | placed    |
      | 2        | shipped   |
      | 3        | completed |
    When the "select order_id, {{ dbt_utils.generate_surrogate_key(['order_id', 'status']) }} as order_key from {{ ref('orders') }}" macro runs
    Then "select order_id, {{ dbt_utils.generate_surrogate_key(['order_id', 'status']) }} as order_key from {{ ref('orders') }}" should have 3 rows

  Scenario: Distinct order_id/status pairs never collide into the same key
    Given the following rows in "orders":
      | order_id | status    |
      | 1        | placed    |
      | 2        | shipped   |
      | 3        | completed |
    When the "select order_id, {{ dbt_utils.generate_surrogate_key(['order_id', 'status']) }} as order_key from {{ ref('orders') }}" macro runs
    Then column "order_key" in "select order_id, {{ dbt_utils.generate_surrogate_key(['order_id', 'status']) }} as order_key from {{ ref('orders') }}" should be unique
