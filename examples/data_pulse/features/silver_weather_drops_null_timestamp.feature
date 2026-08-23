Feature: Silver weather standardization

  Scenario: A row with a missing timestamp is dropped
    Given the following rows in "bronze_weather":
      | timestamp           | temperature | wind_speed | wind_direction | precipitation | cloud_cover | condition | source_id |
      | 2026-08-18 06:00:00 | 18.2        | 12.4       | 220             | 0.0            | 40          | Clear     | brightsky |
      |                     | 19.0        | 10.0       | 200             | 0.0            | 30          | Clear     | brightsky |
    When the "silver_weather" model runs
    Then "silver_weather" should have 1 row
    And the row for source_id "brightsky" should have temperature_c 18.2
