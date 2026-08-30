Feature: generate_surrogate_key produces a stable, deterministic hash

  Scenario: Same input fields always produce the same key
    Given the following rows in "orders":
      | order_id | status  |
      | 1        | placed  |
      | 2        | shipped |
    When the "select order_id, {{ dbt_utils.generate_surrogate_key(['order_id', 'status']) }} as order_key from {{ ref('orders') }} order by order_id" macro runs
    Then the "select order_id, {{ dbt_utils.generate_surrogate_key(['order_id', 'status']) }} as order_key from {{ ref('orders') }} order by order_id" should produce the following rows:
      | order_id | order_key                        |
      | 1        | 3b8d3a0710139623574ed352387c1401 |
      | 2        | 5294b8cfc5826a1b7fe812d14a7c02c4 |
