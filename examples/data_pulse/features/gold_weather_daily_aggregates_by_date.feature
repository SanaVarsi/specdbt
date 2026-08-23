Feature: Gold daily weather aggregation

  Scenario: Two hourly readings on the same date aggregate into one daily row
    Given the following rows in "silver_weather":
      | date       | temperature_c | wind_speed_kmh | precipitation_mm | cloud_cover_pct |
      | 2026-08-18 | 16.0           | 10.0            | 0.0               | 20               |
      | 2026-08-18 | 20.0           | 14.0            | 1.0               | 60               |
    When the "gold_weather_daily" model runs
    Then "gold_weather_daily" should have 1 row
    And the row for date "2026-08-18" should have avg_temp_c 18.0
    And the row for date "2026-08-18" should have hour_count 2
