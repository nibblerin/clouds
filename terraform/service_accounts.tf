resource "google_service_account" "function" {
  account_id = "${local.base}-fn"
  display_name = "Runtime SA of the weather ingestion function"
  depends_on = [google_project_service.apis]
}

resource "google_service_account" "build" {
  account_id = "${local.base}-build"
  display_name = "Cloud Build SA for the weather function"
  depends_on = [google_project_service.apis]
}

resource "google_service_account" "scheduler" {
  account_id = "${local.base}-sched"
  display_name = "Cloud Scheduler SA (invokes the function)"
  depends_on = [google_project_service.apis]
}

resource "google_service_account" "airflow" {
  account_id = "${local.base}-airflow"
  display_name = "SA impersonated by local Airflow"
  depends_on = [google_project_service.apis]
}
