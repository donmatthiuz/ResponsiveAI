# NO importar una base compartida sin inspeccionar sus datos y su ciclo de vida.
resource "google_firestore_database" "orders" {
  project                 = var.project_id
  name                    = var.firestore_database
  location_id             = var.region
  type                    = "FIRESTORE_NATIVE"
  concurrency_mode        = "PESSIMISTIC"
  delete_protection_state = "DELETE_PROTECTION_DISABLED"
  deletion_policy         = "DELETE"
  depends_on              = [google_project_service.apis]
}
