resource "google_bigquery_dataset" "gold" {
  dataset_id                 = var.bq_dataset_id
  location                   = var.data_location
  labels                     = local.labels
  delete_contents_on_destroy = false

  depends_on = [google_project_service.apis]
}

resource "google_bigquery_table" "weather" {
  dataset_id          = google_bigquery_dataset.gold.dataset_id
  table_id            = var.bq_table_id
  labels              = local.labels
  deletion_protection = var.deletion_protection
  schema              = file("${path.module}/schema/weather_realtime.json")

}
