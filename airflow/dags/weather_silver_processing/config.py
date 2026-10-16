from __future__ import annotations

import os
import re

PROJECT = os.environ["GCP_PROJECT_ID"]
BUCKET = os.environ["DATA_BUCKET"]

BQ_DATASET = os.environ.get("BQ_DATASET", "weather_gold")
BQ_TABLE = os.environ.get("BQ_TABLE", "weather_realtime")
BQ_LOCATION = os.environ.get("BQ_LOCATION", "EU")
AIRFLOW_SA = os.environ.get("AIRFLOW_SA_EMAIL")  # impersonation, без ключей

BRONZE_ROOT = "bronze/weather/realtime"
SILVER_ROOT = "silver/weather/realtime"
QUARANTINE_ROOT = "quarantine/weather/realtime"

COLUMNS = [
    "source_object", "event_time", "location_name", "location_lat", "location_lon",
    "location_type", "ingested_at_utc", "weather_temperature", "weather_humidity",
    "weather_windSpeed", "weather_cloudCover", "weather_precipitationProbability",
]

BQ_SCHEMA = [
    {"name": "source_object", "type": "STRING", "mode": "REQUIRED"},
    {"name": "event_time", "type": "TIMESTAMP", "mode": "REQUIRED"},
    {"name": "location_name", "type": "STRING", "mode": "REQUIRED"},
    {"name": "location_lat", "type": "FLOAT", "mode": "NULLABLE"},
    {"name": "location_lon", "type": "FLOAT", "mode": "NULLABLE"},
    {"name": "location_type", "type": "STRING", "mode": "NULLABLE"},
    {"name": "ingested_at_utc", "type": "TIMESTAMP", "mode": "REQUIRED"},
    {"name": "weather_temperature", "type": "FLOAT", "mode": "NULLABLE"},
    {"name": "weather_humidity", "type": "FLOAT", "mode": "NULLABLE"},
    {"name": "weather_windSpeed", "type": "FLOAT", "mode": "NULLABLE"},
    {"name": "weather_cloudCover", "type": "FLOAT", "mode": "NULLABLE"},
    {"name": "weather_precipitationProbability", "type": "FLOAT", "mode": "NULLABLE"},
]

BRONZE_RE = re.compile(
    rf"^{BRONZE_ROOT}/(?P<loc>[^/]+)/(?P<y>\d{{4}})/(?P<m>\d{{2}})/(?P<d>\d{{2}})/(?P<h>\d{{2}})/[^/]+\.json$"
)
