variable "project_id" {
  description = "ID del proyecto dedicado al laboratorio, con facturación activa."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id debe tener entre 6 y 30 caracteres válidos."
  }
}

variable "region" {
  type    = string
  default = "us-central1"
  validation {
    condition     = can(regex("^[a-z]+-[a-z]+[0-9]+$", var.region))
    error_message = "Región de GCP inválida."
  }
}

variable "function_name" {
  type    = string
  default = "orders-api"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,22}[a-z0-9]$", var.function_name))
    error_message = "Usa 2–24 caracteres para dejar espacio al sufijo -build (SA máximo 30)."
  }
}

variable "runtime" {
  type    = string
  default = "python313"
  validation {
    condition     = var.runtime == "python313"
    error_message = "Este laboratorio se verifica con python313."
  }
}

variable "entry_point" {
  type    = string
  default = "handle"
  validation {
    condition     = var.entry_point == "handle"
    error_message = "El contrato requiere handle."
  }
}

variable "source_dir" {
  type    = string
  default = "../backend"
  validation {
    condition     = fileexists("${var.source_dir}/main.py") && fileexists("${var.source_dir}/requirements.txt")
    error_message = "source_dir debe contener main.py y requirements.txt."
  }
}

variable "failure_rate" {
  type    = number
  default = 0.02
  validation {
    condition     = var.failure_rate >= 0 && var.failure_rate <= 1
    error_message = "failure_rate debe estar en [0,1]."
  }
}

variable "extra_latency_ms" {
  type    = number
  default = 0
  validation {
    condition     = var.extra_latency_ms >= 0
    error_message = "extra_latency_ms debe ser no negativa."
  }
}

variable "extra_env" {
  type    = map(string)
  default = {}
}

variable "max_instances" {
  type    = number
  default = 10
  validation {
    condition     = var.max_instances >= 1 && var.max_instances <= 100 && floor(var.max_instances) == var.max_instances
    error_message = "max_instances debe ser un entero entre 1 y 100."
  }
}

variable "concurrency" {
  type    = number
  default = 1
  validation {
    condition     = var.concurrency >= 1 && var.concurrency <= 1000 && floor(var.concurrency) == var.concurrency
    error_message = "concurrency debe ser un entero entre 1 y 1000."
  }
}

variable "allow_unauthenticated" {
  type    = bool
  default = true
}

variable "invoker_members" {
  description = "Identidades roles/run.invoker si la organización prohíbe allUsers."
  type        = set(string)
  default     = []
  validation {
    condition     = alltrue([for member in var.invoker_members : can(regex("^(user|group|serviceAccount):[^ ]+@[^ ]+$", member))])
    error_message = "Miembros IAM inválidos."
  }
}

variable "log_retention_days" {
  type    = number
  default = 30
  validation {
    condition     = var.log_retention_days >= 1 && var.log_retention_days <= 3650 && floor(var.log_retention_days) == var.log_retention_days
    error_message = "Retención entre 1 y 3650 días enteros."
  }
}

variable "student_members" {
  type    = set(string)
  default = []
  validation {
    condition     = alltrue([for member in var.student_members : can(regex("^(user|group|serviceAccount):[^ ]+@[^ ]+$", member))])
    error_message = "Usa user:correo, group:correo o serviceAccount:correo."
  }
}

variable "firestore_database" {
  type    = string
  default = "lab-orders"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,61}[a-z0-9]$", var.firestore_database))
    error_message = "Usa una base dedicada con nombre de 4–63 caracteres."
  }
}

variable "analytics_run_id" {
  type    = string
  default = "pending-run"
  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$", var.analytics_run_id))
    error_message = "run_id inválido."
  }
}

variable "analytics_start_utc" {
  type    = string
  default = "1970-01-01T00:00:00Z"
  validation {
    condition     = can(timeadd(var.analytics_start_utc, "0s"))
    error_message = "Usa RFC3339."
  }
}

variable "analytics_end_utc" {
  type    = string
  default = "1970-01-01T01:02:00Z"
  validation {
    condition     = can(timeadd(var.analytics_end_utc, "0s"))
    error_message = "Usa RFC3339."
  }
}

variable "dashboard_override_file" {
  description = "JSON final exportado de consola; evita eliminar widgets añadidos manualmente. Ruta relativa a infra."
  type        = string
  default     = ""
}
