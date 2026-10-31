locals {
  completion_filter = "resource.type=\"cloud_run_revision\" AND resource.labels.project_id=\"${var.project_id}\" AND resource.labels.service_name=\"${local.service_name}\" AND jsonPayload.message=\"request_completed\""
  queries = {
    for name in ["errors_by_category", "latency_by_tier"] : name => replace(replace(replace(replace(replace(
      file("${path.module}/../observability/queries/${name}.sql"),
      "__PROJECT_ID__", var.project_id), "__SERVICE_NAME__", local.service_name),
    "__RUN_ID__", var.analytics_run_id), "__START_UTC__", var.analytics_start_utc), "__END_UTC__", var.analytics_end_utc)
  }
  dashboard_template = replace(replace(replace(replace(
    file("${path.module}/../observability/dashboard.json"),
    "__PROJECT_ID__", var.project_id), "__SERVICE_NAME__", local.service_name),
    "\"__ERROR_SQL__\"", jsonencode(local.queries.errors_by_category)),
  "\"__LATENCY_SQL__\"", jsonencode(local.queries.latency_by_tier))
}

resource "google_logging_metric" "completed" {
  name        = "lab_request_completed_count"
  description = "Un evento request_completed por solicitud; sin IDs de alta cardinalidad."
  filter      = local.completion_filter
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
    dynamic "labels" {
      for_each = toset(["outcome", "category", "endpoint", "customer_tier"])
      content {
        key        = labels.value
        value_type = "STRING"
      }
    }
  }
  label_extractors = {
    for key in ["outcome", "category", "endpoint", "customer_tier"] : key => "EXTRACT(jsonPayload.${key})"
  }
  depends_on = [google_project_service.apis]
}

resource "google_logging_metric" "latency" {
  name            = "lab_request_latency_ms"
  filter          = local.completion_filter
  value_extractor = "EXTRACT(jsonPayload.latency_ms)"
  description     = "Latencia del backend en ms; límites 0,1,5,10,25,50,100,250,500,1000,2500,5000,10000,30000,60000."
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "ms"
    dynamic "labels" {
      for_each = toset(["endpoint", "customer_tier"])
      content {
        key        = labels.value
        value_type = "STRING"
      }
    }
  }
  label_extractors = {
    endpoint      = "EXTRACT(jsonPayload.endpoint)"
    customer_tier = "EXTRACT(jsonPayload.customer_tier)"
  }
  bucket_options {
    explicit_buckets {
      bounds = [0, 1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000]
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_monitoring_dashboard" "lab" {
  dashboard_json = var.dashboard_override_file != "" ? file(var.dashboard_override_file) : local.dashboard_template
  depends_on = [
    google_logging_metric.completed, google_logging_metric.latency,
    google_logging_project_bucket_config.default,
  ]
}
