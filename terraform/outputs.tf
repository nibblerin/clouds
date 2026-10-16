output "data_bucket" {
  value = google_storage_bucket.data.name
}

output "function_uri" {
  value = google_cloudfunctions2_function.ingest.service_config[0].uri
}

output "scheduler_job" {
  value = google_cloud_scheduler_job.ingest.name
}

output "bigquery_table" {
  value = "${var.project_id}.${google_bigquery_dataset.gold.dataset_id}.${google_bigquery_table.weather.table_id}"
}

output "secret_id" {
  value = google_secret_manager_secret.api_key.secret_id
}

output "service_accounts" {
  value = {
    function  = google_service_account.function.email
    build     = google_service_account.build.email
    scheduler = google_service_account.scheduler.email
    airflow   = google_service_account.airflow.email
  }
}
