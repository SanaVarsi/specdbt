Feature: star selects every real column of a fixture — introspective macro

  Scenario: star expands to the fixture's actual columns, unchanged
    Given the following rows in "orders":
      | order_id | status  |
      | 1        | placed  |
      | 2        | shipped |
    When the "select {{ dbt_utils.star(from=ref('orders')) }} from {{ ref('orders') }} order by order_id" macro runs
    Then the "select {{ dbt_utils.star(from=ref('orders')) }} from {{ ref('orders') }} order by order_id" should produce the following rows:
      | order_id | status  |
      | 1        | placed  |
      | 2        | shipped |
