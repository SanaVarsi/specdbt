Feature: Gold weather anomaly detection

  Scenario: A reading close to the rolling baseline is not flagged
    Given the following rows in "gold_weather_daily":
      | date       | avg_temp_c |
      | 2026-07-21 | 17.8       |
      | 2026-07-22 | 18.1       |
      | 2026-08-19 | 18.5       |
    When the "gold_weather_anomalies" model runs
    Then "gold_weather_anomalies" should have 1 row
    And the row for date "2026-08-19" should have is_anomaly False
    And the row for date "2026-08-19" should have z_score 0.5
