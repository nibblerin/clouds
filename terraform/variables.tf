#input variables for project/region/env/names

variable "project_id" {
  description = "GCP project ID"
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be a valid GCP project id."
  }
}

variable "region" {
  description = "Region for Cloud Function, Cloud Run and Cloud Scheduler"
  type        = string
  default     = "europe-west1"
}

variable "data_location" {
  description = "Location of the data bucket AND BigQuery dataset (must match, e.g. EU or US)"
  type        = string
  default     = "EU"
}

variable "env" {
  description = "Environment name"
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "stage", "prod"], var.env)
    error_message = "env must be one of: dev, stage, prod."
  }
}

variable "name_prefix" {
  description = "Short prefix for resource names"
  type        = string
  default     = "weather"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,9}$", var.name_prefix))
    error_message = "name_prefix: 2-10 chars, lowercase letters, digits, hyphens; must start with a letter."
  }
}

variable "owner" {
  description = "Owner label (team or person)"
  type        = string
  default     = "data-engineering"
  validation {
    condition     = can(regex("^[a-z0-9_-]{1,63}$", var.owner))
    error_message = "owner must match ^[a-z0-9_-]{1,63}$ (GCP label rules)."
  }
}

variable "locations" {
  description = "Locations passed to Tomorrow.io (used as-is for the API and slugified for GCS paths)"
  type        = list(string)
  default     = ["warsaw", "berlin"]
  validation {
    condition     = length(var.locations) > 0
    error_message = "Provide at least one location."
  }
}

variable "api_key_secret_id" {
  description = "Secret Manager secret ID holding the Tomorrow.io API key"
  type        = string
  default     = "tomorrow-io-api-key"
}

variable "schedule" {
  description = "Cron schedule for ingestion"
  type        = string
  default     = "*/10 * * * *"
}

variable "schedule_time_zone" {
  type    = string
  default = "Etc/UTC"
}

variable "bq_dataset_id" {
  type    = string
  default = "weather_gold"
  validation {
    condition     = can(regex("^[A-Za-z0-9_]+$", var.bq_dataset_id))
    error_message = "Dataset id may contain only letters, digits and underscores."
  }
}

variable "bq_table_id" {
  type    = string
  default = "weather_realtime"
}

variable "airflow_operator_members" {
  description = "IAM members (e.g. user:you@example.com) allowed to impersonate the Airflow service account from local Airflow. No SA keys are created."
  type        = list(string)
  default     = []
}

variable "force_destroy" {
  description = "Allow deleting non-empty buckets on destroy. Keep false for safety."
  type        = bool
  default     = false
}

variable "deletion_protection" {
  description = "Protect the BigQuery table from deletion"
  type        = bool
  default     = true
}
