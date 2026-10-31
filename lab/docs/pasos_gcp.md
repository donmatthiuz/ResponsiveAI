# Pasos para completar la validación en Google Cloud

Este documento describe el procedimiento reproducible completo. En la sesión actual el usuario ya confirmó proyecto/facturación y ADC, desplegó la función y ejecutó el smoke GCP. El estado actualizado y la corrección de paneles SQL están en `avance.md`; la hora oficial y el cierre siguen pendientes. El proyecto se eligió explícitamente con el usuario.

## 1. Seleccionar proyecto y facturación en consola

1. Abre [Google Cloud Console](https://console.cloud.google.com/).
2. En el selector superior, crea o selecciona un proyecto destinado al laboratorio. Copia su **ID**, que puede diferir del nombre visible.
3. En **Facturación**, verifica que el proyecto esté vinculado a una cuenta activa.
4. Usa un proyecto propio/de clase donde puedas administrar APIs, cuentas de servicio, IAM, Cloud Functions/Run, Storage, Artifact Registry, Firestore, Logging y Monitoring. Si careces de permisos, pide al administrador los correspondientes a la operación que falle; no agregues Owner a ciegas.

La infraestructura crea roles de runtime/build/estudiantes, pero quien ejecuta Terraform necesita poder asignarlos. Además necesita `iam.serviceAccounts.actAs` sobre build y runtime. Terraform no puede concederse a sí mismo permisos que todavía no tiene.

## 2. Autenticar desde la terminal

Desde el equipo con este repositorio:

```bash
cd /home/donmathiuz/ResponsiveAI/lab
export PATH="$HOME/google-cloud-sdk/bin:/tmp/responsiveai-tools:$PATH"
export LAB_PROJECT='REEMPLAZA_CON_EL_ID_REAL'
gcloud auth login
gcloud config set project "$LAB_PROJECT"
gcloud auth application-default login
gcloud auth application-default set-quota-project "$LAB_PROJECT"
gcloud projects describe "$LAB_PROJECT" --format='value(projectId)'
gcloud billing projects describe "$LAB_PROJECT"
```

Los dos logins abren el navegador y cumplen funciones diferentes: CLI y ADC para Terraform/SDK. No pegues tokens ni claves en el chat. `/tmp/responsiveai-tools/terraform` es la instalación usada en esta sesión; si ya no existe, instala Terraform >=1.5 desde [HashiCorp](https://developer.hashicorp.com/terraform/install). Para `terraform test` hace falta >=1.7. Python debe ser 3.13; el `.venv` existente usa un intérprete descargado en `/tmp`, así que recréalo si se limpia ese directorio.

## 3. Revisar recursos existentes y configurar Terraform

```bash
gcloud services enable firestore.googleapis.com --project="$LAB_PROJECT"
gcloud firestore databases list --project="$LAB_PROJECT"
gcloud logging buckets describe _Default --location=global --project="$LAB_PROJECT"
cd infra
cp -n terraform.tfvars.example terraform.tfvars
```

Edita `infra/terraform.tfvars`: cambia `project_id` al ID real; agrega los correos `student_members` si corresponde. Mantén región `us-central1`, nombre `orders-api`, FAILURE_RATE 0.02 y latencia extra 0 para la corrida de referencia.

Si ya existe `lab-orders`, **no la importes automáticamente**: inspecciona quién la usa y sus datos. Para evitar administrar/eliminar datos ajenos, elige otro `firestore_database` dedicado. `deletion_policy=DELETE` elimina la base administrada al destruir. Si `_Default` no está en `global`, documenta ese impedimento y ajusta el proyecto/alcance antes de continuar: las consultas suministradas esperan la referencia global del PDF.

La habilitación de Analytics sobre `_Default` es permanente. La infraestructura no elimina ese bucket compartido al destruir. [Comportamiento documentado del recurso](https://registry.terraform.io/providers/hashicorp/google/6.50.0/docs/resources/logging_project_bucket_config).

## 4. Revisar y desplegar

Desde `lab/infra/`:

```bash
mkdir -p .build
terraform init
terraform fmt -check
terraform validate
terraform plan -out=tfplan
terraform show -no-color tfplan
terraform apply tfplan
terraform output
```

Revisa nombres y proyecto del plan. No debe incluir recursos ajenos. El runtime `python313` figura en el [soporte oficial](https://docs.cloud.google.com/functions/docs/runtime-support); el despliegue efectivo sigue pendiente de confirmar.

Si el primer build falla por propagación de IAM, espera aproximadamente un minuto y vuelve a ejecutar **plan y apply una vez**. Si se repite, abre Cloud Build → historial del build y revisa la causa. La identidad build tiene `builds.builder`, `storage.objectViewer`, `logging.logWriter` y `artifactregistry.writer` sobre el repositorio de imágenes propio. No repitas indefinidamente ni asignes permisos amplios sin diagnóstico. [Identidades y permisos de build](https://docs.cloud.google.com/functions/docs/building).

Si falla el binding `allUsers` por política de la organización: configura `allow_unauthenticated=false` y `invoker_members=["user:TU_CORREO"]` o una cuenta de servicio; vuelve a revisar/aplicar el plan. En los comandos HTTP siguientes agrega `--auth gcloud`. La opción de impersonación requiere `--impersonate-service-account CORREO` y permisos de generación de tokens sobre esa identidad.

## 5. Configurar URL y comprobar las métricas ANTES del tráfico

```bash
export LAB_URL="$(terraform output -raw function_url)"
export LAB_SERVICE="$(terraform output -raw service_name)"
export LAB_DASHBOARD="$(terraform output -raw dashboard_name)"
gcloud logging metrics describe lab_request_completed_count --project="$LAB_PROJECT" --format=json
gcloud logging metrics describe lab_request_latency_ms --project="$LAB_PROJECT" --format=json
cd ..
.venv/bin/python - <<'PY'
import json, os
from pathlib import Path
for name in ('config.json', 'config.smoke.json'):
    path = Path('simulator') / name
    config = json.loads(path.read_text())
    config['target_url'] = os.environ['LAB_URL']
    path.write_text(json.dumps(config, indent=2) + '\n')
PY
```

Guarda las dos respuestas `metrics describe` como evidencia previa. No existe recuperación automática de logs anteriores al crear las métricas. [Comportamiento de métricas basadas en logs](https://docs.cloud.google.com/logging/docs/logs-based-metrics).

## 6. Verificar contrato, ingestión y dashboard

Desde `lab/`:

```bash
export LAB_CHECK="check-$(date -u +%Y%m%dT%H%M%SZ)"
.venv/bin/python -m scripts.verify_api --target-url "$LAB_URL" \
  --output-dir "evidence/$LAB_CHECK" --run-id "$LAB_CHECK" --probe-failure 300
export LAB_SMOKE="smoke-$(date -u +%Y%m%dT%H%M%SZ)"
.venv/bin/python simulator/simulator.py --config simulator/config.smoke.json \
  --output "evidence/$LAB_SMOKE/requests.csv" --run-id "$LAB_SMOKE" --time-scale 0.002
```

1. Abre **Logging → Logs Explorer** y filtra:

   ```text
   resource.type="cloud_run_revision"
   resource.labels.service_name="orders-api"
   jsonPayload.message="request_completed"
   ```

2. Verifica que `status_code` y `latency_ms` son numéricos, que `request_id` coincide con `http_cases.json`/CSV y que hay logs de éxito, 400, 404, 409 y 500. `--probe-failure` hace un muestreo acotado: si no aparece 500, conserva ese resultado y completa la evidencia con otra prueba; no alteres retrospectivamente los datos.
3. Espera la ingestión hasta que el dashboard muestre solicitudes y latencias. En **Monitoring → Metrics Explorer**, confirma los descriptores `run.googleapis.com/request_count` y `run.googleapis.com/request_latencies`, recurso `cloud_run_revision`, servicio real, unidad ms para latencia y clases de respuesta para volumen.
4. Abre el enlace de `terraform output -raw dashboard_console` desde `infra/`. Verifica gráficas nativas, métricas de logs y panel de logs. Todavía no habrá datos SQL de la corrida oficial: empieza con `pending-run` y fecha 1970 para evitar mezclar pruebas.
5. En **Logging → Observability Analytics** (también llamado Log Analytics), selecciona la vista `PROYECTO.global._Default._Default` e inspecciona una fila. Las consultas usan `json_payload`, `resource.type`, `JSON_VALUE` y `SAFE_CAST`; confirma que el esquema real coincide. [Esquema y consultas SQL oficiales](https://docs.cloud.google.com/logging/docs/analyze/examples).
6. Verifica que una identidad de `student_members` pueda ver el dashboard y los logs. No inicies la hora mientras falte cualquiera de esas señales.

Si la API del proyecto rechaza los widgets SQL preview, crea temporalmente un JSON con solo los cuatro widgets de métricas, logs y texto, úsalo en `dashboard_override_file` y aplica. Después ejecuta las consultas en Analytics, crea sus gráficas y usa **Guardar → Dashboard existente**, eligiendo el mismo dashboard. Exporta y conserva el JSON final antes de otro apply. [Gráficas SQL en dashboards](https://docs.cloud.google.com/logging/docs/analyze/charts).

## 7. Ejecutar la hora oficial

Usa una VM estable o desactiva la suspensión de la laptop. Detén las pruebas paralelas. Confirma configuración oficial: 6000, μ30, σ10, semilla42, invalid_share0.08, escenario electronics [35,45), URL real y `--time-scale 1`.

Desde `lab/`, mantén esta terminal abierta:

```bash
export LAB_RUN="official-$(date -u +%Y%m%dT%H%M%SZ)"
export LAB_EVIDENCE="evidence/$LAB_RUN"
.venv/bin/python simulator/simulator.py --config simulator/config.json \
  --output "$LAB_EVIDENCE/requests.csv" --run-id "$LAB_RUN" --time-scale 1
```

El plan se escribe antes de preparar; luego se confirman los recursos, se esperan 120 s sin tráfico y comienza t0. La ventana de envío dura 3600 s; el drenado de respuestas puede prolongar el proceso. Lee `summary.json`: `status=complete`, `programmed=sent=completed=6000`, `time_scale=1`. Los errores de transporte siguen siendo intentos, pero deben analizarse. Una corrida incompleta no cumple la hora oficial. No reutilices `run_id` ni el directorio de una corrida anterior.

Guarda versiones y la identidad del código en `docs/ejecucion.md` o en la evidencia: versiones Python/Terraform/gcloud, commit y estado de modificaciones; conserva también los locks y hashes de fuentes. No compartas el state ni credenciales.

## 8. Configurar las consultas de ESA corrida y preservar el dashboard

```bash
.venv/bin/python scripts/render_observability.py --project "$LAB_PROJECT" \
  --service "$LAB_SERVICE" --summary "$LAB_EVIDENCE/summary.json" \
  --output-dir "$LAB_EVIDENCE/rendered"
.venv/bin/python scripts/validate_dashboard.py "$LAB_EVIDENCE/rendered/dashboard.json"
```

Para el dashboard que viene de Terraform sin cambios manuales, agrega en `infra/terraform.tfvars`:

```hcl
dashboard_override_file = "../evidence/EL_RUN_REAL/rendered/dashboard.json"
```

Luego, desde `infra/`, ejecuta `terraform plan -out=tfplan`, revisa que solo actualice lo previsto y `terraform apply tfplan`. Alternativamente configura `analytics_run_id`, `analytics_start_utc` y `analytics_end_utc` con el inicio real y el fin del drenado de `summary.json`, sin override.

**Si editaste el dashboard por consola**, primero expórtalo con el script del siguiente paso, copia ese JSON a `observability/dashboard.final.json`, y usa `dashboard_override_file="../observability/dashboard.final.json"`. Así el próximo plan conserva tus widgets. Si conservas nuestros títulos, `render_observability.py --dashboard-source ARCHIVO` puede actualizar sus dos consultas SQL sin quitar otros widgets del `gridLayout`. Para layouts que la consola cambie a mosaic u otra estructura, edita la consulta en consola y vuelve a exportar el JSON final.

En el dashboard selecciona el mismo inicio UTC y fin de drenado que el SQL. Los filtros de dashboard no modifican automáticamente las consultas SQL. No ejecutes otros smoke tests durante esa ventana. La quietud previa evita incluir preparación en el primer intervalo nativo de un minuto. Los percentiles SQL son aproximados; los percentiles de métricas de logs se estiman sobre buckets.

## 9. Exportar evidencia real y analizar

Desde `lab/` y después de esperar la ingestión:

```bash
.venv/bin/python -m scripts.export_evidence --project "$LAB_PROJECT" \
  --evidence-dir "$LAB_EVIDENCE" --dashboard-name "$LAB_DASHBOARD"
.venv/bin/python scripts/analyze.py "$LAB_EVIDENCE" \
  --logs "$LAB_EVIDENCE/logs_sample.jsonl"
```

El exportador obtiene el dashboard real por REST sin perder campos SQL preview, guarda logs JSONL y descriptores de métricas. Los tokens permanecen en memoria. Si los logs aún no aparecen, repite la exportación tras esperar y registra el retraso de ingestión. Las capturas se hacen en consola: guarda `dashboard.png` legible en la evidencia, con los siete paneles exigidos y ventana UTC visible. Puedes usar varias capturas del mismo dashboard si no caben en pantalla.

En Analytics ejecuta los SQL de `rendered/`; configura las dos gráficas SQL y guárdalas en **ese mismo** dashboard si hiciste el fallback por consola. Para una solicitud, vuelve a renderizar con `--request-id ID_DEL_CSV`, ejecuta `correlate_request.sql` y contrasta código, operación y latencias. Conserva evidencia de 2xx/400/404/409/500 de la prueba previa, además de la corrida oficial.

Completa `docs/analisis.md` con los datos reales, tamaños de muestra, tasas por ventana y categoría, p50/p95 por operación/segmento, correlación y discrepancias entre CSV, logs y métricas nativas. El script genera una base cuantitativa; falta interpretar y verificar las métricas del dashboard.

## 10. Destruir solamente el laboratorio después de guardar evidencia

```bash
cd infra
terraform plan -destroy -out=tfplan-destroy
terraform show -no-color tfplan-destroy
terraform apply tfplan-destroy
terraform state list
gcloud functions describe orders-api --gen2 --region=us-central1 --project="$LAB_PROJECT"
gcloud firestore databases list --project="$LAB_PROJECT"
gcloud storage buckets list --project="$LAB_PROJECT"
gcloud artifacts repositories list --location=us-central1 --project="$LAB_PROJECT"
```

`terraform apply tfplan-destroy` ejecuta la destrucción revisada. También se admite `terraform destroy` revisando su confirmación interactiva. Confirma que la función y la base dedicadas ya no existen. La base `lab-orders`, el bucket propio (`force_destroy=true`), el repositorio propio y sus imágenes, IAM administrado, dashboard y métricas deben desaparecer. **No borres recursos ajenos ni buckets administrados sin comprobar a quién pertenecen.**

Las APIs quedan habilitadas (`disable_on_destroy=false`); `_Default`, sus logs/retención y Analytics quedan activos. Pueden quedar buckets de staging de GCF y otros artefactos gestionados por Google. Lista y registra los residuos concretos y la salida de la limpieza en `docs/avance.md` y `docs/ejecucion.md`; no afirmes que se revirtió Analytics. [Residuos del build documentados por Google](https://docs.cloud.google.com/functions/docs/building).
