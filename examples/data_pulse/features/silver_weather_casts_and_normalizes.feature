Feature: Silver weather standardization — casting and normalization

  Scenario: A reading is cast and its condition text is lowercased
    Given the following rows in "bronze_weather":
      | timestamp           | temperature | wind_speed | wind_direction | precipitation | cloud_cover | condition | source_id  |
      | 2026-08-18 07:00:00 | 21.6        | 8.3        | 190             | 2.5            | 75          | RAIN      | dwd_backup |
    When the "silver_weather" model runs
    Then "silver_weather" should have 1 row
    And the row for source_id "dwd_backup" should have condition "rain"
