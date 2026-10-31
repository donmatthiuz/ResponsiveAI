locals {
  services = toset([
    "cloudfunctions.googleapis.com", "run.googleapis.com", "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com", "storage.googleapis.com", "logging.googleapis.com",
    "monitoring.googleapis.com", "iam.googleapis.com", "firestore.googleapis.com",
    "cloudresourcemanager.googleapis.com", "serviceusage.googleapis.com",
  ])
  student_roles = toset([
    "roles/monitoring.editor", "roles/logging.viewer", "roles/logging.configWriter",
    "roles/cloudfunctions.viewer", "roles/logging.viewAccessor",
  ])
  student_grants = {
    for pair in setproduct(var.student_members, local.student_roles) :
    "${pair[0]}|${pair[1]}" => { member = pair[0], role = pair[1] }
  }
  service_name = element(reverse(split("/", google_cloudfunctions2_function.api.service_config[0].service)), 0)
}

resource "google_project_service" "apis" {
  for_each           = local.services
  service            = each.value
  disable_on_destroy = false
}

# _Default es compartido: destroy abandona su configuración; Analytics es permanente.
resource "google_logging_project_bucket_config" "default" {
  project          = var.project_id
  location         = "global"
  bucket_id        = "_Default"
  retention_days   = var.log_retention_days
  enable_analytics = true
  depends_on       = [google_project_service.apis]
}

resource "google_service_account" "runtime" {
  account_id   = "${var.function_name}-run"
  display_name = "Runtime ${var.function_name}"
  depends_on   = [google_project_service.apis]
}

resource "google_service_account" "build" {
  account_id   = "${var.function_name}-build"
  display_name = "Build ${var.function_name}"
  depends_on   = [google_project_service.apis]
}

resource "google_project_iam_member" "runtime_roles" {
  for_each = toset(["roles/logging.logWriter", "roles/monitoring.metricWriter", "roles/datastore.user"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "build_roles" {
  # builder conserva la base del PDF; objectViewer incluye el bucket de staging de GCF.
  for_each = toset(["roles/cloudbuild.builds.builder", "roles/logging.logWriter", "roles/storage.objectViewer"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.build.email}"
}

resource "google_project_iam_member" "students" {
  for_each = local.student_grants
  project  = var.project_id
  role     = each.value.role
  member   = each.value.member
}

resource "google_storage_bucket" "source" {
  name                        = "${var.project_id}-${var.function_name}-src"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
  depends_on                  = [google_project_service.apis]
}

resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = "${var.function_name}-images"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

resource "google_artifact_registry_repository_iam_member" "build" {
  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.images.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.build.email}"
}

data "archive_file" "source" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = "${path.module}/.build/function-source.zip"
  excludes    = ["__pycache__", ".venv", ".pytest_cache", ".env"]
}

resource "google_storage_bucket_object" "source" {
  name   = "function-source-${data.archive_file.source.output_md5}.zip"
  bucket = google_storage_bucket.source.name
  source = data.archive_file.source.output_path
}

resource "google_cloudfunctions2_function" "api" {
  name     = var.function_name
  location = var.region
  labels   = { lab = "observable-api" }

  build_config {
    runtime           = var.runtime
    entry_point       = var.entry_point
    service_account   = google_service_account.build.id
    docker_repository = google_artifact_registry_repository.images.id
    source {
      storage_source {
        bucket = google_storage_bucket.source.name
        object = google_storage_bucket_object.source.name
      }
    }
  }

  service_config {
    available_memory                 = "512Mi"
    available_cpu                    = "1"
    timeout_seconds                  = 60
    min_instance_count               = 0
    max_instance_count               = var.max_instances
    max_instance_request_concurrency = var.concurrency
    service_account_email            = google_service_account.runtime.email
    ingress_settings                 = "ALLOW_ALL"
    environment_variables = merge(var.extra_env, {
      FAILURE_RATE         = tostring(var.failure_rate)
      EXTRA_LATENCY_MS     = tostring(var.extra_latency_ms)
      FIRESTORE_PROJECT_ID = var.project_id
      FIRESTORE_DATABASE   = google_firestore_database.orders.name
    })
  }
  depends_on = [
    google_project_iam_member.build_roles, google_project_iam_member.runtime_roles,
    google_artifact_registry_repository_iam_member.build,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = var.allow_unauthenticated ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = local.service_name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "authenticated" {
  for_each = var.invoker_members
  project  = var.project_id
  location = var.region
  name     = local.service_name
  role     = "roles/run.invoker"
  member   = each.value
}
