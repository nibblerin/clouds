data "archive_file" "function_zip" {
  type = "zip"
  source_dir = "${path.module}/../function"
  output_path = "${path.module}/build/function.zip"
}

resource "google_storage_bucket_object" "function_zip" {
  name = "ingest/${data.archive_file.function_zip.output_md5}.zip"
  bucket = google_storage_bucket.function_source.name
  source = data.archive_file.function_zip.output_path
}

resource "google_cloudfunctions2_function" "ingest" {
  name = "${local.base}-ingest"
  location = var.region
  description = "Fetches realtime weather from Tomorrow.io and stores raw JSON in GCS (bronze)"
  labels = local.labels

  build_config {
    runtime = "python314"
    entry_point = "fetch_weather"
    service_account = google_service_account.build.id

    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.function_zip.name
      }
    }
  }

  service_config {
    available_memory = "256M"
    timeout_seconds = 60
    min_instance_count = 0
    max_instance_count = 2
    ingress_settings = "ALLOW_ALL" # google_cloud_run_v2_service_iam_member will get OIDC-token
    service_account_email = google_service_account.function.email

    environment_variables = {
      GCP_PROJECT = var.project_id
      DATA_BUCKET = google_storage_bucket.data.name
      API_KEY_SECRET_ID = google_secret_manager_secret.api_key.secret_id
      LOCATIONS = join(",", var.locations)
    }
  }

  depends_on = [
    google_project_service.apis,
    google_project_iam_member.build_roles,
    google_storage_bucket_iam_member.build_src_reader,
  ]
}

resource "google_cloud_scheduler_job" "ingest" {
  name        = "${local.base}-ingest-trigger"
  region      = var.region
  description = "Triggers weather ingestion"
  schedule    = var.schedule
  time_zone   = var.schedule_time_zone

  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.ingest.service_config[0].uri

    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = google_cloudfunctions2_function.ingest.service_config[0].uri
    }
  }

  depends_on = [google_project_service.apis]
}
