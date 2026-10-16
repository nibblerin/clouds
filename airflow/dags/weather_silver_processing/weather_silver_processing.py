from __future__ import annotations

from datetime import datetime, timezone

from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator
from airflow.sdk import Param, dag

from weather_silver_processing.config import (
    AIRFLOW_SA, BQ_DATASET, BQ_LOCATION, BQ_SCHEMA, BQ_TABLE, BUCKET, PROJECT,
)
from weather_silver_processing.processing import process_bronze_to_silver

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
