"""Hand-computed the same way as the outlier scenario, with a small deviation:
rolling_avg=18.0, rolling_stddev=1.0, avg_temp_c=18.5 ->
z_score = (18.5 - 18.0) / 1.0 = 0.5  ->  |0.5| is not > 2  ->  is_anomaly = False."""

from specdbt.adapters.base import ExecutionResult

CANNED_RESULTS = {
    "gold_weather_anomalies": ExecutionResult.of(
        rows=[
            {
                "date": "2026-08-19",
                "avg_temp_c": 18.5,
                "rolling_avg": 18.0,
                "rolling_stddev": 1.0,
                "z_score": 0.5,
                "is_anomaly": False,
            }
        ],
    ),
}
