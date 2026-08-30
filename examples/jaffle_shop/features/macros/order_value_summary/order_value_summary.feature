Feature: order_value_summary pairs each order's amount with its value tier

  Composes bucket_order_value — a macro calling another macro — so the
  amount/tier pairing isn't repeated at every call site.

  Scenario: Summary rows carry both the raw amount and its tier
    Given the following rows in "orders":
      | order_id | amount |
      | 1        | 10.00  |
      | 2        | 500.00 |
    When the "select {{ order_value_summary('order_id', 'amount') }} from {{ ref('orders') }} order by order_id" macro runs
    Then the "select {{ order_value_summary('order_id', 'amount') }} from {{ ref('orders') }} order by order_id" should produce the following rows:
      | order_id | amount | value_bucket |
      | 1        | 10.00  | small        |
      | 2        | 500.00 | large        |
