"""Hand-computed from silver_weather.sql: the null-timestamp row is filtered by
WHERE timestamp IS NOT NULL; the remaining row is cast per the SELECT list."""

from specdbt.adapters.base import ExecutionResult

CANNED_RESULTS = {
    "silver_weather": ExecutionResult.of(
        rows=[
            {
                "timestamp": "2026-08-18 06:00:00",
                "hour": "2026-08-18 06:00:00",
                "date": "2026-08-18",
                "temperature_c": 18.2,
                "wind_speed_kmh": 12.4,
                "wind_direction_deg": 220,
                "precipitation_mm": 0.0,
                "cloud_cover_pct": 40,
                "condition": "clear",
                "source_id": "brightsky",
            }
        ],
    ),
}
