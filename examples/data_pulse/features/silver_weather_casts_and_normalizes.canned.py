"""Hand-computed from silver_weather.sql: LOWER(TRIM(condition)) turns
'RAIN' into 'rain'; all other columns are straight casts of the input."""

from specdbt.adapters.base import ExecutionResult

CANNED_RESULTS = {
    "silver_weather": ExecutionResult.of(
        rows=[
            {
                "timestamp": "2026-08-18 07:00:00",
                "hour": "2026-08-18 07:00:00",
                "date": "2026-08-18",
                "temperature_c": 21.6,
                "wind_speed_kmh": 8.3,
                "wind_direction_deg": 190,
                "precipitation_mm": 2.5,
                "cloud_cover_pct": 75,
                "condition": "rain",
                "source_id": "dwd_backup",
            }
        ],
    ),
}
