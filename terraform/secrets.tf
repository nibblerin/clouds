resource "google_secret_manager_secret" "api_key" {
  secret_id = var.api_key_secret_id
  labels    = local.labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}