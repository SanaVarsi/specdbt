Feature: bucket_order_value tiers an order's amount into small/medium/large

  Scenario: Amounts below 50, between 50 and 200, and 200+ land in different tiers
    Given the following rows in "orders":
      | order_id | amount |
      | 1        | 10.00  |
      | 2        | 100.00 |
      | 3        | 500.00 |
    When the "select order_id, amount, {{ bucket_order_value('amount') }} as value_bucket from {{ ref('orders') }} order by order_id" macro runs
    Then the "select order_id, amount, {{ bucket_order_value('amount') }} as value_bucket from {{ ref('orders') }} order by order_id" should produce the following rows:
      | order_id | amount | value_bucket |
      | 1        | 10.00  | small        |
      | 2        | 100.00 | medium       |
      | 3        | 500.00 | large        |

  Scenario: An amount exactly at a threshold lands in the higher tier
    Given the following rows in "orders":
      | order_id | amount |
      | 1        | 50.00  |
      | 2        | 200.00 |
    When the "select order_id, amount, {{ bucket_order_value('amount') }} as value_bucket from {{ ref('orders') }} order by order_id" macro runs
    Then the "select order_id, amount, {{ bucket_order_value('amount') }} as value_bucket from {{ ref('orders') }} order by order_id" should produce the following rows:
      | order_id | amount | value_bucket |
      | 1        | 50.00  | medium       |
      | 2        | 200.00 | large        |

  Scenario: Custom thresholds override the macro's defaults
    Given the following rows in "orders":
      | order_id | amount |
      | 1        | 75.00  |
      | 2        | 500.00 |
    When the "select order_id, amount, {{ bucket_order_value('amount', 100, 1000) }} as value_bucket from {{ ref('orders') }} order by order_id" macro runs
    Then the "select order_id, amount, {{ bucket_order_value('amount', 100, 1000) }} as value_bucket from {{ ref('orders') }} order by order_id" should produce the following rows:
      | order_id | amount | value_bucket |
      | 1        | 75.00  | small        |
      | 2        | 500.00 | medium       |
