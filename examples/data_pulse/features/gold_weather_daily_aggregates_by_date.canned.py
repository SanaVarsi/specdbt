"""Hand-computed from gold_weather_daily.sql for two hourly rows on the same
date: avg_temp_c = (16.0 + 20.0) / 2 = 18.0, hour_count = 2, etc."""

from specdbt.adapters.base import ExecutionResult

CANNED_RESULTS = {
    "gold_weather_daily": ExecutionResult.of(
        rows=[
            {
                "date": "2026-08-18",
                "avg_temp_c": 18.0,
                "max_temp_c": 20.0,
                "min_temp_c": 16.0,
                "avg_wind_speed_kmh": 12.0,
                "max_wind_speed_kmh": 14.0,
                "total_precipitation_mm": 1.0,
                "avg_cloud_cover_pct": 40.0,
                "hour_count": 2,
            }
        ],
    ),
}
