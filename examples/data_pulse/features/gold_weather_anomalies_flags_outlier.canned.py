"""Hand-computed from gold_weather_anomalies.sql's real formula, given an
as-if-already-computed rolling_avg=18.0 and rolling_stddev=1.0 for the target
date (representing a stable ~18C baseline over the trailing window):
z_score = (avg_temp_c - rolling_avg) / rolling_stddev = (32.0 - 18.0) / 1.0 = 14.0
is_anomaly = rolling_stddev > 0 AND abs(z_score) > 2  ->  True."""

from specdbt.adapters.base import ExecutionResult

CANNED_RESULTS = {
    "gold_weather_anomalies": ExecutionResult.of(
        rows=[
            {
                "date": "2026-08-18",
                "avg_temp_c": 32.0,
                "rolling_avg": 18.0,
                "rolling_stddev": 1.0,
                "z_score": 14.0,
                "is_anomaly": True,
            }
        ],
    ),
}
