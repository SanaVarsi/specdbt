Feature: Gold weather anomaly detection — flags an outlier

  Scenario: A sharp spike relative to the rolling baseline is flagged as an anomaly
    Given the following rows in "gold_weather_daily":
      | date       | avg_temp_c |
      | 2026-07-20 | 18.0       |
      | 2026-07-21 | 17.5       |
      | 2026-07-22 | 18.2       |
      | 2026-08-18 | 32.0       |
    When the "gold_weather_anomalies" model runs
    Then "gold_weather_anomalies" should have 1 row
    And the row for date "2026-08-18" should have is_anomaly True
    And the row for date "2026-08-18" should have z_score 14.0
