from datetime import datetime, timezone, timedelta
import json
import logging
from airflow.providers.google.cloud.hooks.gcs import GCSHook

from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator
from airflow.sdk import Param, dag, task
from airflow.sdk.exceptions import AirflowFailException

from weather_silver_processing.config import (
    AIRFLOW_SA, BQ_DATASET, BQ_LOCATION, BQ_SCHEMA, BQ_TABLE, BRONZE_RE, BRONZE_ROOT,
    BUCKET, PROJECT, QUARANTINE_ROOT, SILVER_ROOT,
)
from weather_silver_processing.validation import (
    discover_locations, fmt_ts, normalize_source_path, rows_to_csv, validate_payload,
)
log = logging.getLogger(__name__)


@task(multiple_outputs=True)  
def process_bronze_to_silver(**context):
    params = context["params"]
    run_ts = datetime.now(timezone.utc)
    #source_path not provided ...
    ref = context["dag_run"].logical_date or run_ts

    hook = GCSHook(impersonation_chain=AIRFLOW_SA)

    if params.get("source_path"):
        prefixes = [normalize_source_path(params["source_path"])]
    else:
        locations = discover_locations(hook)
        if not locations:
            raise AirflowFailException(f"No locations found under {BRONZE_ROOT}/")
        log.info("Discovered locations: %s", locations)
        #source_path not provided -> process previous UTC hour.
        prev = ref.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        prefixes = [f"{BRONZE_ROOT}/{loc}/{prev:%Y/%m/%d/%H}/" for loc in locations]
    log.info("Source prefixes: %s", prefixes)

    objects = []
    for prefix in prefixes:
        objects += [o for o in hook.list(BUCKET, prefix=prefix) if o.endswith(".json")]
    if not objects:
        raise AirflowFailException(f"No .json files found under {prefixes}")
    log.info("Found %d JSON files", len(objects))

    ingested_at = fmt_ts(run_ts)
    #Deduplication before output
    seen, valid, rejected = set(), [], []
#Read all JSON files under source prefix
    for obj in sorted(objects):
        source = f"gs://{BUCKET}/{obj}"
        m = BRONZE_RE.match(obj)
        if not m:
            log.warning("Unexpected path layout, skipping %s", source)
            rejected.append({"source_object": source, "error": "unexpected object path"})
            continue
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
            "event_time": fmt_ts(rec["event_time"]),
            "location_name": rec["location_name"],
            "location_lat": rec["location_lat"],
            "location_lon": rec["location_lon"],
            "location_type": rec["location_type"],
            "ingested_at_utc": ingested_at,
            **{f"weather_{k}": v for k, v in rec["weather"].items()},
        }

        part = (m["loc"], m["y"], m["m"], m["d"], m["h"])
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
        hook.upload(BUCKET, out, data=rows_to_csv(rows), mime_type="text/csv")
        log.info("Wrote %d rows to gs://%s/%s", len(rows), BUCKET, out)
        silver_objects.append(out)

    return {"silver_objects": silver_objects, "rows": len(valid), "rejected": len(rejected)}


@dag(
    dag_id="weather_silver_processing",
    start_date=datetime(2026, 10, 15, tzinfo=timezone.utc),
    schedule=None, 
    catchup=False,
    max_active_runs=1,
    params={
        "source_path": Param(
            None, type=["null", "string"],
            description="Optional GCS prefix (gs://bucket/prefix or prefix). Default: previous UTC hour.",
        )
    },
    tags=["weather", "gcp"],
)
def weather_silver_processing():
    process = process_bronze_to_silver()

    GCSToBigQueryOperator(
        task_id="load_silver_to_bigquery",
        bucket=BUCKET,
        source_objects=process["silver_objects"],  
        destination_project_dataset_table=f"{PROJECT}.{BQ_DATASET}.{BQ_TABLE}",
        source_format="CSV",
        skip_leading_rows=1,
        schema_fields=BQ_SCHEMA,
        write_disposition="WRITE_APPEND",
        create_disposition="CREATE_NEVER",
        location=BQ_LOCATION,
        impersonation_chain=AIRFLOW_SA,
    )

weather_silver_processing()
