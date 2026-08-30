Feature: order_history loads incrementally by order_date

  @unit @incremental_model
  Scenario: Full refresh loads every row from stg_orders
    Given the following rows in "stg_orders":
      | order_id | customer_id | order_date | status  |
      | 1        | 1           | 2018-01-01 | placed  |
      | 2        | 1           | 2018-01-02 | shipped |
    When the "order_history" model runs
    Then the "order_history" should produce the following rows:
      | order_id | customer_id | order_date | status  |
      | 1        | 1           | 2018-01-01 | placed  |
      | 2        | 1           | 2018-01-02 | shipped |

  @unit @incremental_model
  Scenario: Incremental mode only loads rows newer than what's already in the table
    Given the following rows in "stg_orders":
      | order_id | customer_id | order_date | status    |
      | 1        | 1           | 2018-01-01 | placed    |
      | 2        | 1           | 2018-01-02 | shipped   |
      | 3        | 1           | 2018-01-03 | completed |
    And the following rows already in "order_history":
      | order_id | customer_id | order_date | status |
      | 1        | 1           | 2018-01-01 | placed |
    When the "order_history" model runs
    Then the "order_history" should produce the following rows:
      | order_id | customer_id | order_date | status    |
      | 2        | 1           | 2018-01-02 | shipped   |
      | 3        | 1           | 2018-01-03 | completed |

  @unit @incremental_model
  Scenario: Incremental mode loads nothing when the source has no rows newer than what's already loaded
    Given the following rows in "stg_orders":
      | order_id | customer_id | order_date | status |
      | 1        | 1           | 2018-01-01 | placed |
    And the following rows already in "order_history":
      | order_id | customer_id | order_date | status |
      | 1        | 1           | 2018-01-01 | placed |
    When the "order_history" model runs
    Then the "order_history" should produce the following rows:
      | order_id | customer_id | order_date | status |
