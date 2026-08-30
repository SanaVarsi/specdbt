Feature: pivot_sum pivots category rows into one summed column per category

  Generalizes the hardcoded payment_methods loop in models/orders.sql
  into a reusable, parameterized macro (a Jinja for-loop under the hood).

  Scenario: Splits payment amounts per order into one column per payment method
    Given the following rows in "payments":
      | order_id | payment_method | amount |
      | 1        | credit_card    | 10.00  |
      | 1        | coupon         | 5.00   |
      | 2        | credit_card    | 20.00  |
    When the "select order_id, {{ pivot_sum('payment_method', ['credit_card', 'coupon'], 'amount') }} from {{ ref('payments') }} group by order_id order by order_id" macro runs
    Then the "select order_id, {{ pivot_sum('payment_method', ['credit_card', 'coupon'], 'amount') }} from {{ ref('payments') }} group by order_id order by order_id" should produce the following rows:
      | order_id | credit_card_amount | coupon_amount |
      | 1        | 10.00               | 5.00           |
      | 2        | 20.00               | 0.00           |
