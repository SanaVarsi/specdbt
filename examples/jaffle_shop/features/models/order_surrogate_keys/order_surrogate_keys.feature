Feature: order_surrogate_keys derives a stable hash key per order

  A macro (dbt_utils.generate_surrogate_key) consumed inside a real model,
  not called standalone — the hash values below match
  generate_surrogate_key.feature's, since both hash the same order_id and
  status pair.

  @unit
  Scenario: Same order_id and status always produce the same key
    Given the following rows in "stg_orders":
      | order_id | status  |
      | 1        | placed  |
      | 2        | shipped |
    When the "order_surrogate_keys" model runs
    Then the "order_surrogate_keys" should produce the following rows:
      | order_id | order_key                        |
      | 1        | 3b8d3a0710139623574ed352387c1401 |
      | 2        | 5294b8cfc5826a1b7fe812d14a7c02c4 |
