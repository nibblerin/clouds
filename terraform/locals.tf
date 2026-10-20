locals {
  base = "${var.name_prefix}-${var.env}"
  labels = {
    app = "weather-pipeline"
    env = var.env
    owner = var.owner
    managed_by = "terraform"
  }
  data_bucket_name = "${local.base}-${var.project_id}-data"
  src_bucket_name = "${local.base}-${var.project_id}-fn-src"

  apis = [
    "cloudfunctions.googleapis.com",
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudscheduler.googleapis.com",
    "secretmanager.googleapis.com",
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
  ]
}