# Locals (S)
# All environment-specific values are switched on `terraform.workspace`.
# Workspaces in use: "sit" and "prod".
locals {
  project_id        = "ask-finance-${terraform.workspace}"
  region            = "us-central1"
  github_repository = "baohq1595/Ask-Finance"

  ask_finance_min_instance_count = terraform.workspace == "prod" ? 1 : 0
  ask_finance_max_instance_count = terraform.workspace == "prod" ? 10 : 3
}
# Locals (E)


# Provider (S)
provider "google" {
  project = local.project_id
  region  = local.region
}
# Provider (E)


# Enable APIs (S)
variable "gcp_service_list" {
  description = "The list of APIs necessary for the project"
  type        = list(string)
  default = [
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "aiplatform.googleapis.com",
    "sts.googleapis.com",
    "logging.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ]
}

resource "google_project_service" "gcp_services" {
  for_each           = toset(var.gcp_service_list)
  service            = each.key
  disable_on_destroy = false
}
# Enable APIs (E)


# Service Accounts (S)
resource "google_service_account" "sa_ask_finance_runtime" {
  account_id   = "sa-ask-finance-runtime"
  display_name = "Ask Finance Cloud Run runtime"
}

resource "google_service_account" "sa_ask_finance_ci" {
  account_id   = "sa-ask-finance-ci"
  display_name = "Ask Finance CI/CD (GitHub Actions)"
}
# Service Accounts (E)


# Artifact Registry (S)
resource "google_artifact_registry_repository" "ask_finance" {
  location      = local.region
  repository_id = "ask-finance"
  description   = "Container images for Ask Finance"
  format        = "DOCKER"

  labels = {
    "ai_product" : "ask-finance"
  }

  depends_on = [
    google_project_service.gcp_services
  ]
}
# Artifact Registry (E)


# Service (S)
resource "google_cloud_run_v2_service" "ask_finance_service" {
  name     = "ask-finance-api"
  location = local.region

  template {
    labels = {
      "ai_product" : "ask-finance"
    }

    service_account = google_service_account.sa_ask_finance_runtime.email

    containers {
      # the image here is just a placeholder. The actual image will be pushed by CD pipeline
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          # CPU & Memory usage limit (per container)
          cpu    = "1000m"
          memory = "1024Mi"
        }
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = local.project_id
      }
      env {
        name  = "VERTEX_LOCATION"
        value = local.region
      }
      env {
        name  = "ASK_FINANCE_MODEL"
        value = "gemini-2.5-flash"
      }
      env {
        name  = "ASK_FINANCE_DATA_DIR"
        value = "/app/data"
      }
      env {
        name  = "ASK_FINANCE_LOGS_DIR"
        value = "/tmp/ask_finance_logs"
      }
    }

    scaling {
      min_instance_count = local.ask_finance_min_instance_count
      max_instance_count = local.ask_finance_max_instance_count
    }
  }

  depends_on = [
    google_project_service.gcp_services
  ]

  lifecycle {
    # these changes are ignored so that we can manage deployments via CD pipeline
    ignore_changes = [
      client,
      client_version,
      template[0].containers[0].image,
    ]
  }
}
# Service (E)


# IAM (S)
data "google_iam_policy" "noauth" {
  binding {
    role = "roles/run.invoker"
    members = [
      "allUsers",
    ]
  }
}

resource "google_cloud_run_service_iam_policy" "noauth" {
  location    = google_cloud_run_v2_service.ask_finance_service.location
  project     = google_cloud_run_v2_service.ask_finance_service.project
  service     = google_cloud_run_v2_service.ask_finance_service.name
  policy_data = data.google_iam_policy.noauth.policy_data
}

resource "google_project_iam_member" "vertex_ai_user_role" {
  project = google_cloud_run_v2_service.ask_finance_service.project
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.sa_ask_finance_runtime.email}"
}

resource "google_project_iam_member" "logging_writer_role" {
  project = google_cloud_run_v2_service.ask_finance_service.project
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.sa_ask_finance_runtime.email}"
}

resource "google_artifact_registry_repository_iam_member" "ci_ar_writer" {
  location   = google_artifact_registry_repository.ask_finance.location
  repository = google_artifact_registry_repository.ask_finance.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.sa_ask_finance_ci.email}"
}

resource "google_project_iam_member" "ci_run_developer" {
  project = google_cloud_run_v2_service.ask_finance_service.project
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.sa_ask_finance_ci.email}"
}

resource "google_service_account_iam_member" "ci_uses_runtime_sa" {
  service_account_id = google_service_account.sa_ask_finance_runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.sa_ask_finance_ci.email}"
}
# IAM (E)


# Workload Identity Federation - GitHub OIDC (S)
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-actions"
  display_name              = "GitHub Actions"

  depends_on = [
    google_project_service.gcp_services
  ]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }

  # Only tokens from this repo can authenticate.
  attribute_condition = "assertion.repository == \"${local.github_repository}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_wif_binding" {
  service_account_id = google_service_account.sa_ask_finance_ci.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${local.github_repository}"
}
# Workload Identity Federation (E)


# Outputs (S)
output "cloud_run_service_url" {
  value       = google_cloud_run_v2_service.ask_finance_service.uri
  description = "HTTPS URL of the Cloud Run service. Use for ASK_FINANCE_API_URL in the UI."
}

output "artifact_registry_repository" {
  value       = "${google_artifact_registry_repository.ask_finance.location}-docker.pkg.dev/${local.project_id}/${google_artifact_registry_repository.ask_finance.repository_id}"
  description = "Fully-qualified Artifact Registry host/path for docker push."
}

output "github_actions_variables" {
  description = "Copy into GitHub repo Settings -> Secrets and variables -> Actions -> Variables."
  value = {
    GCP_PROJECT_ID            = local.project_id
    GCP_REGION                = local.region
    WIF_PROVIDER              = google_iam_workload_identity_pool_provider.github.name
    WIF_SERVICE_ACCOUNT       = google_service_account.sa_ask_finance_ci.email
    CLOUD_RUN_SERVICE_ACCOUNT = google_service_account.sa_ask_finance_runtime.email
  }
}
# Outputs (E)
