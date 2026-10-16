terraform {
  required_version = "1.16.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "6.8.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.6"
    }
  }
}


