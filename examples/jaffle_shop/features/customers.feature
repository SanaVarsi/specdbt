Feature: customers aggregates order and payment history per customer

  @unit
  Scenario: Computes order stats and lifetime value for a customer with two completed orders
    Given the following rows in "stg_customers":
      | customer_id | first_name | last_name |
      | 1           | Michael    | P.        |
    And the following rows in "stg_orders":
      | order_id | customer_id | order_date | status    |
      | 10       | 1           | 2018-01-01 | completed |
      | 11       | 1           | 2018-02-01 | completed |
    And the following rows in "stg_payments":
      | payment_id | order_id | payment_method | amount |
      | 100        | 10       | credit_card    | 10.00  |
      | 101        | 11       | credit_card    | 20.00  |
    When the "customers" model runs
    Then the "customers" should produce the following rows:
      | customer_id | first_name | last_name | first_order | most_recent_order | number_of_orders | customer_lifetime_value |
      | 1           | Michael    | P.        | 2018-01-01  | 2018-02-01         | 2                 | 30.00                    |
