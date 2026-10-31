# Terraform >=1.7 para estas pruebas opcionales. El despliegue conserva mínimo 1.5.
# Todos los recursos Google son simulados: no prueba permisos ni existencia en GCP.
mock_provider "google" {}

variables {
  project_id = "demo-observable-lab"
}

run "local_plan" {
  command = plan

  assert {
    condition     = google_cloudfunctions2_function.api.build_config[0].runtime == "python313"
    error_message = "Runtime incorrecto."
  }
  assert {
    condition     = google_cloudfunctions2_function.api.build_config[0].entry_point == "handle"
    error_message = "Entrada incorrecta."
  }
  assert {
    condition     = google_cloudfunctions2_function.api.service_config[0].max_instance_request_concurrency == 1
    error_message = "Concurrencia distinta a la especificada."
  }
  assert {
    condition     = google_firestore_database.orders.deletion_policy == "DELETE"
    error_message = "La base dedicada debe limpiarse al destruir el laboratorio."
  }
  assert {
    condition     = google_logging_metric.latency.metric_descriptor[0].unit == "ms"
    error_message = "Unidad de latencia incorrecta."
  }
}

run "reject_long_sa_name" {
  command = plan
  variables {
    function_name = "this-name-would-overflow-the-build-service-account"
  }
  expect_failures = [var.function_name]
}

run "reject_failure_probability" {
  command = plan
  variables {
    failure_rate = 1.1
  }
  expect_failures = [var.failure_rate]
}

run "reject_negative_latency" {
  command = plan
  variables {
    extra_latency_ms = -1
  }
  expect_failures = [var.extra_latency_ms]
}
