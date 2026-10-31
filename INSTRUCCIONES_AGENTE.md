# Instrucciones para desarrollar el laboratorio: API serverless observable en GCP

Fuente principal: [Laboratorio_API_observable_GCP.pdf](Laboratorio_API_observable_GCP.pdf), 10 páginas. Este documento convierte el enunciado en un plan ejecutable para un agente de desarrollo. La implementación todavía está pendiente.

## 1. Misión y alcance

Desarrolla una API HTTP en Python para gestionar pedidos, despliégala en **Cloud Run functions de segunda generación mediante Terraform**, genera una hora de tráfico concurrente y analiza sus resultados en **un único dashboard de Cloud Monitoring**.

El resultado debe permitir seguir una solicitud desde el CSV del simulador hasta el log del backend y explicar el volumen, los errores y la latencia por atributos de negocio.

Implementa código, infraestructura, observabilidad, pruebas y documentación. Conserva el PDF como referencia. La interfaz de usuario será el dashboard de GCP; el laboratorio no requiere una aplicación web adicional.

### Reglas de trabajo del agente

1. Inspecciona el directorio y las instrucciones locales antes de modificar archivos. Conserva los cambios previos del usuario, incluidas eliminaciones ya presentes en Git.
2. Sigue las fases de este documento y registra su estado en `lab/docs/avance.md`: pendiente, en curso, validado o bloqueado por un dato externo concreto.
3. Distingue resultados comprobados de resultados esperados. Una prueba local o acelerada no acredita un despliegue ni una hora de tráfico real.
4. Resuelve las decisiones rutinarias con los valores definidos aquí. Si falta un proyecto, credencial o permiso, termina el trabajo local y señala exactamente qué falta para la fase de GCP.
5. Usa dependencias compatibles con Python 3.13 y registra las versiones verificadas. Consulta documentación oficial si cambia el esquema del proveedor o de los servicios.
6. Entrega comandos reproducibles, evidencia y limitaciones. No declares el laboratorio terminado mientras queden criterios de aceptación sin verificar.

## 2. Requisitos obligatorios del PDF

| ID | Requisito | Referencia |
| --- | --- | --- |
| R01 | API Python con entrada `handle`, dominio pequeño y al menos tres operaciones. | p. 1 |
| R02 | Respuestas válidas y errores 400 por payload, 404 por recurso inexistente y 409 por cambio de estado imposible. | p. 1 |
| R03 | `FAILURE_RATE` controla fallas HTTP 500 y `EXTRA_LATENCY_MS` añade latencia. | p. 1 |
| R04 | Una línea JSON en stdout al terminar cada solicitud, con los campos exigidos y al menos dos atributos de negocio. | p. 2 |
| R05 | Simulador de una hora; `n_requests` instantes con distribución normal truncada entre 0 y 60 minutos; envíos sin esperar la respuesta anterior. | p. 2 |
| R06 | Mezclar operaciones válidas, payloads inválidos, IDs inexistentes y secuencias imposibles; aplicar `invalid_share` y `scenarios`. | p. 2 |
| R07 | ID único en `X-Request-ID` y CSV con programación, envío, operación, intención, respuesta y latencia del cliente. | p. 2 |
| R08 | Infraestructura Terraform basada en los archivos, recursos y parámetros suministrados. | pp. 3–9 |
| R09 | Outputs `function_url`, `log_analytics_view`, `dashboards_console` y `log_analytics_console`. | p. 9 |
| R10 | Un dashboard con métricas nativas, métricas basadas en logs, gráficas SQL de Log Analytics y panel de logs. | p. 10 |
| R11 | Crear las métricas basadas en logs antes de ejecutar el simulador. | p. 10 |
| R12 | Destruir los recursos del laboratorio al finalizar, después de preservar los resultados. | pp. 2–3 |

## 3. Decisiones de implementación

Las siguientes decisiones completan vacíos del enunciado. **No son requisitos literales del PDF**; son la solución predeterminada para que el agente pueda avanzar.

| Tema | Decisión |
| --- | --- |
| Dominio | Pedidos con operaciones crear, consultar y cancelar. |
| Estado | `created → cancelled`; cancelar nuevamente devuelve 409. |
| Persistencia | Firestore en modo nativo, en una base dedicada `lab-orders`. Agregarlo a Terraform y a las dependencias. Evita perder o separar pedidos entre instancias. |
| Acceso a datos | SDK de servidor con la identidad de ejecución y permisos IAM de datos; credenciales ADC en desarrollo. |
| Desarrollo local | Functions Framework, pruebas con repositorio sustituible y emulador de Firestore para integración. |
| Atributos | `category`, `customer_tier` y `amount`; usar vocabularios acotados para categoría y segmento. |
| Mezcla base | 50 % crear, 30 % consultar y 20 % cancelar; categorías `electronics`, `books`, `clothing` equiprobables; segmentos `standard`, `premium` equiprobables. |
| `invalid_share` | Probabilidad base de producir un error de cliente intencional, no un conteo exacto. Dividir los tipos 400/404/409 de manera equiprobable entre los casos aplicables. |
| `double_errors` | En `electronics`, durante `[35,45)` minutos, duplicar la probabilidad de solicitud inválida: 0.08 → 0.16. No cambia `FAILURE_RATE`. |
| Preparación | Crear los pedidos necesarios antes del inicio medido, con IDs separados de los del tráfico. Excluirlos del CSV principal y del análisis de la hora. |
| Reintentos | No reintentar automáticamente solicitudes del tráfico: cada envío representa un intento y una fila. Los reintentos de preparación se registran aparte. |

El escenario puede elevar la proporción global de inválidas por encima del 8 %. No se exige que la cantidad observada de errores se duplique exactamente: depende del muestreo, del volumen y de la categoría.

Firestore es una ampliación de la infraestructura del PDF. Usa una base dedicada; si ya existe, inspecciónala y documenta su uso antes de administrar su ciclo de vida con Terraform. Mantén los datos de cada ejecución separados mediante `run_id` o una colección propia. Las transiciones deben ser atómicas; las transacciones permiten comprobar el estado antes de actualizarlo. [Transacciones de Firestore](https://docs.cloud.google.com/firestore/native/docs/manage-data/transactions).

## 4. Estructura de entrega

Conserva la estructura mínima del PDF y agrega archivos de apoyo con responsabilidades claras:

```text
INSTRUCCIONES_AGENTE.md
Laboratorio_API_observable_GCP.pdf
lab/
  README.md
  .gitignore
  requirements-dev.txt
  backend/
    main.py
    requirements.txt
    repository.py
  infra/
    versions.tf
    variables.tf
    main.tf
    outputs.tf
    terraform.tfvars.example
    terraform.tfvars             # configuración local real
    observability.tf
    firestore.tf
    .terraform.lock.hcl
  simulator/
    simulator.py
    requirements.txt
    config.json
    config.smoke.json
    requests.csv                # generado durante la ejecución
  observability/
    dashboard.json
    queries/
      traffic_by_minute.sql
      errors_by_category.sql
      latency_by_tier.sql
      correlate_request.sql
  tests/
    test_backend.py
    test_simulator.py
    test_repository_integration.py
  docs/
    avance.md
    decisiones.md
    ejecucion.md
    analisis.md
  evidence/
    <run_id>/
      config.json
      schedule.csv
      requests.csv
      summary.json
      dashboard.json
      dashboard.png
      logs_sample.jsonl
```

`dashboard.json` debe reflejar el dashboard realmente configurado, incluyendo los widgets añadidos por consola. Ignora `.venv/`, `.terraform/`, `.build/`, credenciales, `*.tfstate*` y archivos locales sensibles. Versiona ejemplos sin secretos y el lockfile de Terraform. Conserva las evidencias necesarias sin incluir credenciales.

## 5. Contrato del backend

### Operaciones y payloads

La entrada HTTP se llama `handle`. Implementa el enrutamiento dentro de Functions Framework; todas las respuestas serán JSON y devolverán el `X-Request-ID` recibido, o uno generado si faltaba. [Functions Framework para Python](https://github.com/GoogleCloudPlatform/functions-framework-python).

| Método y ruta | Entrada | Resultado |
| --- | --- | --- |
| `POST /orders` | JSON con `category`, `customer_tier`, `amount`. | 201, pedido con ID generado y estado `created`. |
| `GET /orders/{id}` | ID existente. | 200, datos y estado del pedido. |
| `POST /orders/{id}/cancel` | ID existente en estado `created`. | 200, estado `cancelled`. |

Reglas:

- `category ∈ {electronics, books, clothing}`; `customer_tier ∈ {standard, premium}`; `amount` es numérico, finito y mayor que cero. Rechaza booleanos como montos.
- JSON malformado, campos faltantes o valores inválidos devuelven 400 con `error_type=invalid_payload`.
- ID inexistente devuelve 404 con `error_type=not_found`.
- Cancelar un pedido ya cancelado devuelve 409 con `error_type=invalid_state`.
- Una ruta desconocida devuelve 404; un método no permitido devuelve 405. Ambos generan el log de finalización.
- Una falla artificial devuelve 500 con `error_type=simulated_failure`; una excepción imprevista devuelve 500 con `error_type=internal_error` y un mensaje público genérico.
- Una falla simulada se decide después de validar la solicitud y antes de modificar datos. Los casos inválidos conservan su 400/404/409. No confirmes una escritura y luego respondas con un 500 artificial.
- Valida `FAILURE_RATE ∈ [0,1]` y `EXTRA_LATENCY_MS ≥ 0`. Usa por defecto 0.02 y 0. La demora artificial se aplica a todas las solicitudes atendidas y queda incluida en la latencia registrada.
- La cancelación debe volver a comprobar el estado dentro de una transacción. Dos cancelaciones concurrentes de un pedido activo deben producir un único cambio de estado.

### Logging estructurado

Emite exactamente un evento de aplicación `request_completed` por solicitud que termina en el manejador, incluidos errores de validación y excepciones. Centraliza la emisión al finalizar y evita duplicarla en cada rama. Mide con reloj monotónico y escribe JSON de una sola línea en stdout. [Logging estructurado de GCP](https://docs.cloud.google.com/logging/docs/structured-logging).

Ejemplo ilustrativo del esquema, no evidencia de una ejecución:

```json
{"severity":"INFO","message":"request_completed","request_id":"run-001-request-00001","endpoint":"POST /orders","status_code":201,"outcome":"success","error_type":null,"latency_ms":42.3,"category":"electronics","customer_tier":"premium","amount":125.5,"run_id":"run-001"}
```

| Campo | Regla |
| --- | --- |
| `severity` | `INFO` para 2xx, `WARNING` para 4xx, `ERROR` para 5xx. |
| `message` | Siempre `request_completed`. |
| `request_id` | Copiar `X-Request-ID`; generar ID si falta. |
| `endpoint` | Método y ruta normalizada, por ejemplo `POST /orders/{id}/cancel`. |
| `status_code` | Entero HTTP realmente devuelto. |
| `outcome` | `success`, `client_error` o `server_error` según código. |
| `error_type` | `null` en éxito; categoría estable en error. |
| `latency_ms` | Número no negativo; incluye demora artificial y acceso al almacenamiento. |
| Atributos de negocio | Incluir siempre `category`, `customer_tier`, `amount`; usar `unknown` o `null` cuando no sean recuperables. |
| `run_id` | Ampliación para aislar preparación, smoke test y corrida oficial. |

Para consultas o cancelaciones, toma los atributos del pedido almacenado. Para errores sin pedido o sin payload utilizable, el simulador puede enviar `X-Lab-Category` y `X-Lab-Customer-Tier`, validados contra los vocabularios anteriores; son metadatos sintéticos del laboratorio. Usa `X-Lab-Run-ID` para transmitir `run_id`. No uses estos headers para autorizar operaciones ni para reemplazar datos válidos del recurso.

## 6. Contrato del simulador

### Configuración principal

Mantén los valores de referencia del PDF:

```json
{
  "target_url": "https://<salida-function_url-de-terraform>",
  "n_requests": 6000,
  "mu_min": 30,
  "sigma_min": 10,
  "invalid_share": 0.08,
  "seed": 42,
  "scenarios": [
    {"start_min": 35, "end_min": 45, "effect": "double_errors", "category": "electronics"}
  ]
}
```

Valida URL, entero positivo de solicitudes, `sigma_min > 0`, probabilidades y escenarios dentro de `[0,60]` con inicio menor que fin. Rechaza efectos desconocidos y escenarios superpuestos para una misma categoría, mientras solo exista `double_errors`.

### Programación y concurrencia

1. Usa un generador NumPy inicializado con `seed` para preparar el plan. Genera valores `N(mu_min, sigma_min)` en minutos, descarta los que quedan fuera de `[0,60]` y remuestrea hasta obtener exactamente `n_requests`. En la corrida oficial estos valores serán 42, 30, 10 y 6000, respectivamente. No uses `clip`: produciría acumulaciones en los extremos. [Generador normal de NumPy](https://numpy.org/doc/stable/reference/random/generated/numpy.random.Generator.normal.html).
2. Ordena los instantes y precomputa operación, atributos, intención y escenario. La misma semilla/configuración debe reproducir el plan; las respuestas y los tiempos reales pueden variar.
3. Guarda el plan antes de enviar tráfico. Usa IDs únicos por corrida y solicitud; la unicidad entre corridas puede depender de un `run_id` nuevo.
4. Prepara suficientes pedidos activos para consultas y cancelaciones válidas, y pedidos ya cancelados para provocar 409. Reserva un pedido distinto para cada cancelación válida; las consultas válidas pueden reutilizar otros pedidos.
5. No dependas de que una creación del tráfico finalice para programar otra solicitud. La preparación ocurre antes del reloj de la hora y tiene su propio registro; confirma su resultado y repón los pedidos cuya preparación falle de forma transitoria. Limita la preparación a tres intentos por recurso; si persiste el fallo o hay un problema de permisos, conserva el diagnóstico y no inicies la corrida oficial con datos incompletos.
6. Usa `asyncio` y un `httpx.AsyncClient` reutilizable. Lanza cada tarea según su plazo calculado con reloj monotónico, sin esperar la respuesta de la tarea anterior. Configura conexiones y timeout para la carga prevista. [HTTPX asíncrono](https://www.python-httpx.org/async/).
7. Mantén la ventana oficial de envío en 3600 segundos desde `t0`. Al finalizar, espera las solicitudes pendientes y cierra cliente/CSV. La espera final puede extender el tiempo total del proceso.
8. Registra retrasos de despacho respecto del plan. Si límites de conexiones, saturación o suspensión de la laptop alteran los envíos, conserva los datos y explica la desviación.
9. Proporciona `--dry-run` para generar el plan sin tráfico y `--time-scale` para smoke tests acelerados. Valor oficial: 1. Marca toda ejecución acelerada como prueba y no como cumplimiento de la hora.

Define una interfaz de línea de comandos estable con `--config`, `--output`, `--run-id`, `--dry-run` y `--time-scale`. Describe ejemplos ejecutables en el README. Mantén la aleatoriedad de preparación separada de la del plan para que sus reintentos no cambien el calendario.

### Errores intencionales y escenarios

Para cada instante programado, calcula la probabilidad efectiva de invalidez usando su minuto y categoría: `invalid_share` fuera de escenarios y `min(1, 2 * invalid_share)` cuando coincida uno de tipo `double_errors`. Lee categoría y límites desde `scenarios`. Con la configuración oficial, fuera del escenario es 0.08; dentro de `[35,45)` para `electronics` es 0.16. Clasifica la ventana por instante programado para conservar la reproducibilidad.

En eventos inválidos selecciona un tipo aplicable y ajusta la operación: payload inválido → crear; ID inexistente → consultar o cancelar; estado imposible → cancelar un pedido previamente cancelado. Documenta que esto puede desplazar ligeramente la mezcla final de operaciones. Los eventos válidos conservan la mezcla base.

Guarda separadamente el evento intencionado y el resultado real. Las fallas artificiales del servidor y los fallos de red pueden cambiar el resultado observado, y no deben confundirse con errores de cliente planificados.

### CSV y resumen

Escribe una fila por intento incluso si ocurre timeout o fallo de conexión. Serializa las escrituras mediante un único escritor o mecanismo equivalente; conserva las filas ya escritas ante una interrupción.

Columnas mínimas definidas para esta implementación:

```text
run_id,request_id,scheduled_at_utc,scheduled_offset_s,sent_at_utc,
dispatch_delay_ms,operation,intended_event,expected_status_code,
status_code,client_latency_ms,transport_error,category,customer_tier,scenario
```

Usa UTC en ISO 8601 para fechas y milisegundos numéricos para latencias. `status_code` queda vacío cuando no hubo respuesta HTTP; `transport_error` explica el fallo. `expected_status_code` expresa el resultado funcional sin la inyección de fallas. Define `sent_at_utc` como inicio del intento del cliente y documenta cualquier espera interna del pool.

Genera `summary.json` con configuración, semilla, ventana temporal, cantidad programada/enviada/completada, códigos HTTP, errores de transporte, mezcla de intenciones, percentiles de latencia y retrasos de despacho. Una corrida interrumpida debe identificarse como incompleta.

## 7. Infraestructura con Terraform

Usa como base el HCL de las pp. 3–9 del PDF. Corrige saltos de línea introducidos por la extracción, verifica el esquema real del proveedor y registra cualquier ajuste en `docs/decisiones.md`.

### Recursos y valores

- Terraform `>= 1.5`; proveedor Google `>= 6.0`; proveedor archive `>= 2.4`. Registra las versiones efectivamente probadas y conserva `.terraform.lock.hcl`.
- Región `us-central1`, función `orders-api`, runtime `python313`, entrada `handle` y fuentes `../backend`. Verifica el soporte del runtime al ejecutar el despliegue. [Soporte de runtimes](https://docs.cloud.google.com/functions/docs/runtime-support).
- APIs: `cloudfunctions.googleapis.com`, `run.googleapis.com`, `cloudbuild.googleapis.com`, `artifactregistry.googleapis.com`, `storage.googleapis.com`, `logging.googleapis.com`, `monitoring.googleapis.com`, `iam.googleapis.com`; agrega `firestore.googleapis.com` por la persistencia elegida.
- Cuentas de servicio separadas para build y ejecución; roles de estudiantes del PDF mediante `student_members`.
- Bucket de fuentes con acceso uniforme, ZIP generado y nombre del objeto con hash para provocar un despliegue cuando cambie el código. Crea `.build/` si la herramienta lo necesita y excluye cachés/archivos locales del ZIP.
- `google_cloudfunctions2_function`: 512 MiB, 1 CPU, timeout 60 s, mínimo 0 instancias, máximo 10, concurrencia 1, ingress `ALLOW_ALL`.
- Variables de entorno `FAILURE_RATE=0.02`, `EXTRA_LATENCY_MS=0`, más proyecto/base de Firestore según el SDK.
- `allow_unauthenticated=true` como en el PDF, con `roles/run.invoker` para `allUsers` sobre el servicio real. Si la organización lo prohíbe, documenta la restricción e implementa invocación autenticada en el simulador.
- `_Default` en `global`, retención de 30 días y Analytics habilitado, según el PDF. Esa habilitación es permanente y `destroy` no la revierte.
- Base Firestore dedicada y permisos de datos para runtime, por ejemplo `roles/datastore.user`. Documenta cómo conectar el SDK a esa base y al emulador. [IAM para clientes de servidor de Firestore](https://docs.cloud.google.com/firestore/native/docs/security/iam).
- Métricas basadas en logs y dashboard definidos como infraestructura cuando el proveedor los soporte; preservar/exportar la configuración final si algún widget requiere consola.

### Verificaciones necesarias

1. Valida nombres y rangos de variables. Considera los límites de nombres al añadir sufijos `-run` y `-build` a las cuentas de servicio.
2. Verifica permisos de build para leer fuentes, escribir imágenes y emitir logs. Además de los roles del PDF, configura permisos que falten con el alcance necesario; la documentación enumera `roles/storage.objectViewer`, `roles/artifactregistry.writer` y `roles/logging.logWriter` para builds con identidad propia. [Build de funciones](https://docs.cloud.google.com/functions/docs/building).
3. Comprueba los permisos de la identidad que despliega para habilitar APIs, administrar los recursos y actuar como las cuentas de servicio. No agregues roles amplios a ciegas para resolver errores.
4. Conserva los cuatro outputs del PDF. Verifica que `function_url` sea invocable; usa el atributo admitido por la versión elegida, por ejemplo `service_config[0].uri`. Confirma el nombre del servicio al configurar IAM. [Recurso Terraform de la función](https://raw.githubusercontent.com/hashicorp/terraform-provider-google/main/website/docs/r/cloudfunctions2_function.html.markdown).
5. Si falla el primer build por propagación inicial, espera aproximadamente un minuto y reintenta una vez, como propone el PDF. Si se repite, inspecciona los logs y corrige la causa.
6. Ejecuta `terraform fmt -check`, `terraform init`, `terraform validate` y revisa `terraform plan` antes de aplicar. El despliegue real requiere proyecto, facturación y credenciales disponibles.

## 8. Observabilidad y dashboard único

### Preguntas que debe responder

1. ¿El volumen se concentra alrededor del minuto 30 como indica la distribución normal?
2. ¿Qué proporción de solicitudes termina en 2xx, 4xx y 5xx?
3. ¿Aumenta la tasa de errores de cliente de `electronics` entre los minutos 35 y 45 frente a su línea base y otras categorías?
4. ¿Cómo varían p50/p95 de latencia según operación y segmento de cliente?
5. ¿Qué ocurrió con una solicitud concreta y cómo se relaciona con el CSV?

### Métricas basadas en logs: antes del tráfico

Crea al menos:

| Métrica propuesta | Tipo y contenido |
| --- | --- |
| `lab_request_completed_count` | Contador de eventos de finalización; etiquetas `outcome`, `category`, `endpoint`, `customer_tier`. |
| `lab_request_latency_ms` | Distribución extraída de `latency_ms`, unidad ms y buckets documentados; etiquetas `endpoint`, `customer_tier`. |

Filtra por proyecto/servicio correcto y `jsonPayload.message="request_completed"`, verificando primero el formato real del evento ingerido. No cuentes simultáneamente los logs automáticos de HTTP y los de aplicación. Usa `unknown` de forma consistente para atributos ausentes. No agregues IDs de solicitudes, pedidos o corridas como etiquetas de métricas.

Las métricas de usuario solo procesan logs recibidos después de su creación; no recuperan automáticamente los ya almacenados. Comprueba que existan antes de iniciar la corrida oficial. [Métricas basadas en logs](https://docs.cloud.google.com/logging/docs/logs-based-metrics).

### Paneles mínimos del mismo dashboard

| Panel | Fuente | Configuración esperada |
| --- | --- | --- |
| Solicitudes por minuto y clase HTTP | Nativa | `run.googleapis.com/request_count`, recurso `cloud_run_revision`, separado por clase de respuesta. |
| Latencia p50/p95 | Nativa | `run.googleapis.com/request_latencies`, con unidades y agregación correctas. |
| Resultados por categoría | Basada en logs | Contador de finalizaciones separado por `outcome` y `category`. |
| Latencia por operación/segmento | Basada en logs | Distribución de `latency_ms`, percentil p95. |
| Tasa de error por minuto y categoría | SQL de Analytics | Errores/total; comparar `electronics` con las demás categorías durante el escenario. |
| Latencia por segmento | SQL de Analytics | Totales y percentiles por `customer_tier`, con datos convertidos a tipos numéricos. |
| Eventos de la API | Panel de logs | Logs de finalización, con investigación por `request_id` y `run_id`. |

Verifica los descriptores realmente disponibles en el servicio desplegado. Las métricas nativas anteriores pertenecen a Cloud Run y usan el recurso `cloud_run_revision`. [Métricas de solicitudes y latencia](https://docs.cloud.google.com/stackdriver/docs/solutions/slo-monitoring/sli-metrics/req-resp-metrics).

### SQL y configuración de widgets

- Usa la vista devuelta por `log_analytics_view`, cuya referencia base en el PDF es `` `<PROJECT_ID>.global._Default._Default` ``.
- Guarda consultas ejecutables para tráfico por minuto, tasa de errores por categoría, latencia por segmento y búsqueda por request ID. Parametriza o documenta los valores de proyecto, inicio/fin y corrida.
- Inspecciona el esquema de Analytics antes de escribir las consultas: sus nombres de campos pueden diferir de los de Logs Explorer. Extrae y convierte valores JSON de forma explícita y maneja nulos/divisiones por cero.
- Usa los mismos límites UTC para las gráficas de la ejecución. En SQL filtra también por `run_id`; para métricas nativas y basadas en logs usa una ventana sin tráfico de preparación ni smoke tests.
- Configura tasas como errores/solicitudes con el mismo agrupamiento e intervalo. No interpretes el aumento de un conteo como aumento de probabilidad sin revisar el volumen.
- Crea las gráficas SQL en Analytics y guárdalas en el mismo dashboard de Monitoring. Los filtros de dashboard no se aplican automáticamente a esos widgets; verifica sus filtros y tiempos. [Gráficas SQL en dashboards](https://docs.cloud.google.com/logging/docs/analyze/charts).
- Añade el panel de logs y confirma que los miembros previstos pueden verlo. [Panel de logs en Monitoring](https://docs.cloud.google.com/monitoring/charts/view-logs).
- Exporta el JSON final y captura evidencia legible de las cuatro fuentes exigidas. Si Terraform no conserva algún widget SQL, documenta su creación por consola y evita que una aplicación posterior lo elimine.

## 9. Fases de ejecución y validación

| Fase | Trabajo | Condición para avanzar |
| --- | --- | --- |
| 1. Preparación | Inspeccionar proyecto, crear estructura, dependencias y ejemplos de configuración. | Entorno local reproducible y parámetros externos identificados. |
| 2. Backend | Implementar contrato, repositorio, estados, fallas y logs. | Pruebas funcionales y de logging aprobadas. |
| 3. Simulador | Implementar plan reproducible, preparación, concurrencia, escenarios, CSV y resumen. | Dry-run y smoke test local aprobados. |
| 4. Infraestructura y despliegue | Adaptar Terraform, incluir Firestore, IAM y outputs; validar, revisar plan y desplegar en GCP cuando estén disponibles los datos externos. | Formato y validación aprobados; función desplegada y URL disponible. |
| 5. Observabilidad | Crear métricas, consultas y dashboard. | Métricas creadas y prueba de ingestión verificada. |
| 6. Smoke en GCP | Comprobar rutas, estado compartido y correlación en la función desplegada. | API invocable; señales visibles; errores previstos comprobados. |
| 7. Corrida oficial | Preparar recursos, registrar `t0`, ejecutar 6000 solicitudes durante una hora. | CSV completo, resumen y ventana real registrados. |
| 8. Análisis | Completar dashboard, investigar escenario y contrastar fuentes. | Informe y evidencias guardados. |
| 9. Cierre | Preservar resultados y destruir recursos propios del laboratorio. | Limpieza registrada y recursos residuales identificados. |

### Pruebas significativas

- Backend: crear/consultar/cancelar, entradas inválidas, recurso inexistente, cancelación repetida y cancelaciones concurrentes. Comprobar consistencia entre código, cuerpo y log.
- Fallas: con tasa 0 no se inyectan 500; con tasa 1 una operación válida devuelve 500 antes de escribir; los errores de cliente mantienen su código. Controlar el generador aleatorio en pruebas.
- Latencia: verificar la demora artificial y su inclusión en el evento, con tolerancia al tiempo real de ejecución.
- Logging: un evento final por caso atendido, esquema completo, ID propagado y `error_type` coherente.
- Persistencia: dos clientes o procesos distintos consultan el mismo pedido; la transición es atómica. Usar emulador o integración real, no solo un diccionario de pruebas.
- Plan: exactamente `n_requests` instantes dentro de la hora, reproducibilidad, validación de configuración y límites `[35,45)` del escenario.
- Concurrencia: con un servidor de prueba lento, una segunda solicitud empieza antes de que termine la anterior; comprobar el calendario y sus retrasos.
- CSV: una fila por intento, IDs únicos, respuesta ausente ante fallo de transporte y recuperación del archivo parcial.
- Infraestructura/observabilidad: validar Terraform, invocar URL real y comprobar que los filtros, métricas, SQL y panel de logs muestran las solicitudes de prueba.

No uses tolerancias estadísticas rígidas sobre una única corrida para exigir exactamente 8 % de inválidas, 2 % de fallas o el doble de errores. Prueba la lógica de probabilidades y analiza después las frecuencias observadas.

## 10. Operación y análisis final

El README debe documentar instalación del entorno, uso del emulador, arranque local con Functions Framework, pruebas, dry-run y smoke test. Incluye comandos completos acordes con la CLI realmente implementada.

Para GCP, documenta desde `lab/infra/`:

```bash
gcloud auth application-default login
cp terraform.tfvars.example terraform.tfvars
# Completar project_id y los parámetros reales antes de continuar.
terraform init
terraform fmt -check
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
terraform output -raw function_url
```

Completa la URL en `simulator/config.json`. Antes de la hora oficial confirma métricas creadas, accesibilidad, preparación terminada y ausencia de smoke tests concurrentes. Ejecuta la corrida en una laptop sin suspensión o una VM estable. Guarda hora UTC inicial/final, configuración, versión del código y versiones de herramientas en `docs/ejecucion.md`.

El informe `docs/analisis.md` debe responder las cinco preguntas del dashboard y distinguir:

- Intención del simulador frente a resultado HTTP observado.
- Errores de cliente, fallas artificiales, excepciones reales y errores de transporte.
- Latencia del backend frente a la del cliente y retraso de despacho.
- Línea base frente a ventana del escenario, comparando tasas y tamaños de muestra.
- CSV, logs de aplicación y métricas nativas: explicar diferencias por preparación, ventanas, ingestión, timeouts o solicitudes que no alcanzaron el manejador.

Conserva evidencia de solicitudes exitosas y de 400, 404, 409 y 500, con sus IDs y logs correlacionados. Espera la ingestión antes de concluir que falta una señal. Registra cualquier validación pendiente con su causa real.

Al concluir y guardar evidencias, ejecuta `terraform destroy` sobre el estado del laboratorio. Revisa lo que se eliminará, especialmente la base de datos y el bucket con `force_destroy`. No incluyas recursos compartidos ajenos en la destrucción. Documenta que las APIs con `disable_on_destroy=false`, la habilitación de Analytics y algunos artefactos administrados por GCP pueden permanecer; verifica y registra residuos concretos.

## 11. Criterios de aceptación y entrega del agente

- [ ] Se conserva la estructura mínima del PDF y existe README reproducible.
- [ ] La función `handle` implementa las tres operaciones y los códigos especificados.
- [ ] Los pedidos funcionan entre instancias y las transiciones son atómicas.
- [ ] `FAILURE_RATE` y `EXTRA_LATENCY_MS` funcionan y están documentadas.
- [ ] Los logs JSON contienen todos los campos obligatorios y al menos dos atributos de negocio.
- [ ] El simulador genera exactamente el plan configurado y despacha de forma concurrente.
- [ ] `double_errors` está implementado según la semántica explícita de este documento.
- [ ] El CSV registra un intento por fila, incluidos fallos de transporte.
- [ ] Las pruebas locales relevantes y la validación de Terraform pasan.
- [ ] La API está desplegada en GCP y sus cuatro outputs son correctos.
- [ ] Las métricas basadas en logs existían antes del tráfico oficial.
- [ ] Se completó una ventana real de 3600 segundos con 6000 intentos programados; se documentan los retrasos reales.
- [ ] Un único dashboard integra métricas nativas, métricas de logs, gráficas SQL y panel de logs.
- [ ] Configuración, CSV, resumen, consultas, JSON del dashboard y capturas reales están guardados.
- [ ] El análisis responde las preguntas con datos de la corrida y explica discrepancias.
- [ ] La limpieza final está verificada o su estado pendiente queda identificado con precisión.

Al entregar, informa qué archivos desarrollaste, cómo ejecutar el proyecto, qué verificaciones realizaste y sus resultados. Incluye URL de la función/dashboard cuando existan, estado de la limpieza y cualquier bloqueo externo pendiente. Mantén separados **implementación local completada** y **laboratorio completo validado en GCP** si aún no se pudo ejecutar la fase de nube.
