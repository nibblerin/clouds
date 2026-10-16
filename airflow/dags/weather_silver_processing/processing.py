import csv
import io
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from airflow.sdk.exceptions import AirflowFailException
from airflow.providers.google.cloud.hooks.gcs import GCSHook
from airflow.sdk import task

from weather_silver_processing.config import (
    AIRFLOW_SA, BRONZE_RE, BRONZE_ROOT, BUCKET, COLUMNS, QUARANTINE_ROOT, SILVER_ROOT,
)
from weather_silver_processing.validation import validate_payload

log = logging.getLogger(__name__)

def _fmt_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def discover_locations(hook: GCSHook) -> list[str]:
    iterator = hook.get_conn().bucket(BUCKET).list_blobs(
        prefix=f"{BRONZE_ROOT}/", delimiter="/"
    )
    list(iterator)  
    return sorted(p.rstrip("/").rsplit("/", 1)[-1] for p in iterator.prefixes)


def _normalize_source_path(source_path: str) -> str:
    p = source_path.strip()
    if p.startswith("gs://"):
        bucket, _, prefix = p[5:].partition("/")
        if bucket != BUCKET:
            raise AirflowFailException(f"source_path bucket {bucket!r} != {BUCKET!r}")
        p = prefix
    return p.lstrip("/")

def _fmt_value(key, v):
    if v is None:
        return ""
    if isinstance(v, float) and key.startswith("weather_"):
        return f"{v:.2f}"
    return v


def _csv_bytes(rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: _fmt_value(k, r[k]) for k in COLUMNS})
    return buf.getvalue()

@task(multiple_outputs=True)  
def process_bronze_to_silver(**context):
    params = context["params"]
    run_ts = datetime.now(timezone.utc)
    #source_path not provided -> process previous UTC hour.

    ref = context["dag_run"].logical_date or run_ts

    hook = GCSHook(impersonation_chain=AIRFLOW_SA)

    if params.get("source_path"):
        prefixes = [_normalize_source_path(params["source_path"])]
    else:
        locations = discover_locations(hook)
        if not locations:
            raise AirflowFailException(f"No locations found under {BRONZE_ROOT}/")
        log.info("Discovered locations: %s", locations)
        prev = ref.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        prefixes = [f"{BRONZE_ROOT}/{loc}/{prev:%Y/%m/%d/%H}/" for loc in locations]
    log.info("Source prefixes: %s", prefixes)

    objects = []
    for prefix in prefixes:
        objects += [o for o in hook.list(BUCKET, prefix=prefix) if o.endswith(".json")]
    if not objects:
        raise AirflowFailException(f"No .json files found under {prefixes}")
    log.info("Found %d JSON files", len(objects))

    ingested_at = _fmt_ts(run_ts)
    #Deduplication before output
    seen, valid, rejected = set(), [], []
#Read all JSON files under source prefix
    for obj in sorted(objects):
        source = f"gs://{BUCKET}/{obj}"
        try:
            payload = json.loads(hook.download(BUCKET, obj))
        except Exception as exc:
            log.warning("Invalid JSON %s: %s", source, exc)
            rejected.append({"source_object": source, "error": f"json parse: {exc}"})
            continue
#Validate:Check validation rules section. Drop invalid records with warning logs or save them separately.

        rec, err = validate_payload(payload)
        if err:
            log.warning("Dropping %s: %s", source, err)
            rejected.append({"source_object": source, "error": err})
            continue

        key = (rec["location_name"], rec["event_time"])
        if key in seen:
            log.warning("Duplicate %s dropped (%s)", key, source)
            continue
        seen.add(key)

        row = {
            "source_object": source,
            "event_time": _fmt_ts(rec["event_time"]),
            "location_name": rec["location_name"],
            "location_lat": rec["location_lat"],
            "location_lon": rec["location_lon"],
            "location_type": rec["location_type"],
            "ingested_at_utc": ingested_at,
            **{f"weather_{k}": v for k, v in rec["weather"].items()},
        }

        m = BRONZE_RE.match(obj)
        part = (
            (m["loc"], m["y"], m["m"], m["d"], m["h"]) if m
            else (_slug(rec["location_name"]), *rec["event_time"].strftime("%Y %m %d %H").split())
        )
        valid.append((part, row))

    if rejected:
        rej_obj = f"{QUARANTINE_ROOT}/{run_ts:%Y%m%dT%H%M%SZ}_rejected.jsonl"
        hook.upload(BUCKET, rej_obj,
                    data="\n".join(json.dumps(r) for r in rejected) + "\n",
                    mime_type="application/x-ndjson")
        log.warning("%d rejected records saved to gs://%s/%s", len(rejected), BUCKET, rej_obj)
#Final output check:if no valid records remain after validation, fail the DAG.

    if not valid:
        raise AirflowFailException("No valid records remain after validation")
#Load data to .csv file into silver layer 
    groups: dict[tuple, list[dict]] = {}
    for part, row in valid:
        groups.setdefault(part, []).append(row)

    silver_objects = []
    for (loc, y, mo, d, h), rows in groups.items():
        out = f"{SILVER_ROOT}/{loc}/{y}/{mo}/{d}/{h}/{run_ts:%Y%m%dT%H%M%SZ}.csv"
        hook.upload(BUCKET, out, data=_csv_bytes(rows), mime_type="text/csv")
        log.info("Wrote %d rows to gs://%s/%s", len(rows), BUCKET, out)
        silver_objects.append(out)

    return {"silver_objects": silver_objects, "rows": len(valid), "rejected": len(rejected)}


