import json
import logging
import os
import re
from datetime import datetime, timezone

import functions_framework
import requests
from google.cloud import secretmanager, storage

API_URL = "https://api.tomorrow.io/v4/weather/realtime"

logging.getLogger().setLevel(logging.INFO)
_storage = storage.Client()
_api_key = None

def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _get_api_key() -> str:
    global _api_key
    if _api_key is None:
        name = (
            f"projects/{os.environ['GCP_PROJECT']}/secrets/"
            f"{os.environ['API_KEY_SECRET_ID']}/versions/latest"
        )
        resp = secretmanager.SecretManagerServiceClient().access_secret_version(name=name)
        _api_key = resp.payload.data.decode("utf-8").strip()
    return _api_key

def _ingest(location: str, bucket, now: datetime) -> str:
    resp = requests.get(
        API_URL,
        params={"location": location, "units": "metric"},
        headers={"apikey": _get_api_key(), "accept": "application/json"},
        timeout=20,
    )
    resp.raise_for_status()

    object_name = (
        f"bronze/weather/realtime/{_slug(location)}/"
        f"{now:%Y/%m/%d/%H}/{now:%Y%m%dT%H%M%SZ}.json"
    )
    bucket.blob(object_name).upload_from_string(resp.content, content_type="application/json")
    return f"gs://{bucket.name}/{object_name}"

#functions_framework позволяет объявить Python-функцию как HTTP-обработчик для Cloud Functions
@functions_framework.http
def fetch_weather(request):
    configured = [x.strip() for x in os.environ["LOCATIONS"].split(",") if x.strip()]
    requested = request.args.get("location")
    # either fetch a single configured location or all of them
    # unknown locations are rejected with 400.
    if requested:
        if requested not in configured:
            return (json.dumps({"error": "location not configured"}), 400)
        locations = [requested]
    else:
        locations = configured
    
    bucket = _storage.bucket(os.environ["DATA_BUCKET"])
    now = datetime.now(timezone.utc)
    written, failed = [], []

    for loc in locations:
        try:
            written.append(_ingest(loc, bucket, now))
        except requests.HTTPError as exc:
            logging.error("API error for %s: status=%s", loc, exc.response.status_code)
            failed.append(loc)
        except Exception as exc:  # exc can be sensitive
            logging.error("Failure for %s: %s", loc, type(exc).__name__)
            failed.append(loc)

    body = json.dumps({"written": written, "failed": failed})
    return (body, 502 if failed else 200, {"Content-Type": "application/json"})
