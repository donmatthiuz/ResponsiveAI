# Laboratorio: API observable de pedidos en GCP

Implementación del PDF original, conservado en la raíz del repositorio. La entrega está en `lab/`; la interfaz es un dashboard de Cloud Monitoring.

**Estado:** implementación, despliegue y hora oficial de 6000 intentos verificados, con 6000 logs correlacionados. El [reporte principal está en el README de la raíz](../README.md), con análisis, capturas y conciliación de métricas. La limpieza de GCP sigue pendiente. Consulta [avance](docs/avance.md), [evidencia de ejecución](docs/ejecucion.md) y la [guía paso a paso de GCP](docs/pasos_gcp.md).

## Preparación local

Desde la raíz del repositorio, con Python 3.13:

```bash
cd /home/donmathiuz/ResponsiveAI/lab
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
```

Si usas `uv`: `uv venv --python 3.13 .venv` y `uv pip install --python .venv/bin/python -r requirements-lock.txt`. `requirements-dev.txt` define dependencias directas; `requirements-lock.txt` registra las versiones probadas. Backend y simulador también tienen dependencias independientes. El entorno `.venv` de esta sesión ya está instalado.

## Firestore emulado y API

Requiere Java 21 y el componente oficial de Firestore de gcloud. En una terminal:

```bash
gcloud components install cloud-firestore-emulator
gcloud emulators firestore start --host-port=127.0.0.1:8085 --project=demo-observable-lab
```

En otra terminal, desde `lab/`:

```bash
source .venv/bin/activate
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8085
export FIRESTORE_PROJECT_ID=demo-observable-lab
export FIRESTORE_DATABASE=lab-orders
export FAILURE_RATE=0.02
export EXTRA_LATENCY_MS=0
export DEBUG=false
functions-framework --source=backend/main.py --target=handle --host=127.0.0.1 --port=8080
```

El SDK se conecta a la base nombrada `lab-orders`; el emulador crea bases nombradas de forma implícita. No requiere credenciales reales. Sin `FIRESTORE_EMULATOR_HOST`, usa ADC y la identidad de ejecución de GCP. La aplicación nunca usa memoria como reemplazo de Firestore.

## Contrato HTTP

| Método | Ruta | Resultado funcional |
| --- | --- | --- |
| POST | `/orders` | 201 con `order.id` y estado `created` |
| GET | `/orders/{id}` | 200 con el pedido |
| POST | `/orders/{id}/cancel` | 200, transición atómica a `cancelled` |

```bash
curl -i http://127.0.0.1:8080/orders \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: ejemplo-001' -H 'X-Lab-Run-ID: ejemplo' \
  -d '{"category":"books","customer_tier":"premium","amount":12.5}'
```

Usa el mismo `X-Lab-Run-ID` para crear, consultar y cancelar: las colecciones se separan por corrida. Omitirlo usa `unscoped`. Payload inválido → 400; recurso/ruta ausente → 404; cancelación repetida → 409; método incorrecto → 405. Las respuestas incluyen `request_id` y `X-Request-ID`. Los errores tienen `error.type` y un mensaje público.

`FAILURE_RATE` (predeterminado 0.02) se decide después de validar y antes de escribir; `EXTRA_LATENCY_MS` (0) se aplica a todos los casos. Una configuración inválida impide arrancar. Cada solicitud atendida emite un evento JSON `request_completed` en stdout, con datos de negocio y fase `preparation` o `traffic`.

## Verificaciones

Desde `lab/`, con el emulador activo:

```bash
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 .venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Sin emulador se omite explícitamente la prueba de integración; eso no acredita persistencia entre procesos. El emulador y la suite completa sí se ejecutaron en esta sesión. Para verificar HTTP contra la API activa:

```bash
.venv/bin/python -m scripts.verify_api --target-url http://127.0.0.1:8080 \
  --output-dir evidence/contract-nuevo --run-id contract-nuevo --probe-failure 300
```

Esta herramienta puede reintentar comprobaciones previas a la corrida y registra cada intento; el simulador medido nunca reintenta tráfico. El muestreo de 500 es probabilístico; consulta `observed_500`.

## Simulador

Plan oficial reproducible, sin enviar solicitudes:

```bash
.venv/bin/python simulator/simulator.py --config simulator/config.json \
  --output evidence/plan-nuevo/requests.csv --run-id plan-nuevo --dry-run
```

Smoke local de 60 intentos, ventana comprimida a 7.2 s:

```bash
.venv/bin/python simulator/simulator.py --config simulator/config.smoke.json \
  --output evidence/smoke-nuevo/requests.csv --run-id smoke-nuevo --time-scale 0.002
```

No sobrescribe evidencia. Cada ejecución necesita otro directorio y `run_id`. La configuración oficial contiene 6000 solicitudes, semilla 42, normal truncada μ=30/σ=10 y escenario `double_errors` en electronics durante [35,45). No se usa `clip`. Las inválidas pueden desplazar la mezcla final 50/30/20 de operaciones.

La preparación reserva pedidos distintos para cancelaciones válidas, reutiliza consultas por categoría/segmento y crea pedidos cancelados para 409. Reintenta recursos transitorios como máximo tres veces; falla sin iniciar el reloj si faltan datos. Se registra aparte con `phase=preparation`, usando la misma corrida para acceder a su colección. En modo de una hora hay 120 s de quietud después de preparar para separar las agregaciones nativas por minuto.

Un cliente HTTPX reutilizable permite hasta 200 conexiones y 50 keep-alive; timeouts: 70 s total por fase HTTPX, 10 s conexión/pool. No es un límite total de pared de 70 s: HTTPX limita cada fase de conexión, lectura, escritura y pool. `sent_at_utc` es el comienzo del intento cliente, antes de obtener token/pool; esas esperas están incluidas en la latencia cliente. Las respuestas pueden terminar después de la ventana de envío. Una suspensión que exceda la ventana impide enviar el resto y marca la corrida incompleta.

CSV: una fila por intento iniciado, incluso cancelación, timeout o desconexión; los que no tienen respuesta HTTP dejan `status_code` vacío. El escritor hace flush por fila. Ctrl+C conserva filas y resumen incompleto; un cierre abrupto del sistema puede impedir escribir el resumen final, y habrá que reconstruirlo desde el CSV. No se garantiza recuperación frente a pérdida de energía del disco.

Autenticación alternativa si `allUsers` está prohibido: agrega `--auth gcloud`; opcionalmente `--impersonate-service-account CORREO` para obtener ID tokens con audiencia explícita. Se renuevan cada 40 minutos. La cuenta necesita `roles/run.invoker`; la impersonación también requiere permisos sobre esa cuenta. No se guardan tokens en evidencia.

## Infraestructura y observabilidad

En `infra/` están la función Gen2, Firestore dedicado, identidades build/runtime, fuentes con hash, repositorio de imágenes, IAM, APIs, métricas basadas en logs y un dashboard de ocho widgets. Cuatro outputs obligatorios: `function_url`, `log_analytics_view`, `dashboards_console` y `log_analytics_console`. Se añaden enlaces directos al dashboard y nombre real del servicio.

```bash
cd infra
mkdir -p .build
terraform init
terraform fmt -check
terraform validate
terraform test    # Opcional, Terraform >=1.7; Google simulado, sin despliegue
```

El lockfile fija Google 6.50.0 y archive 2.8.1. El dashboard usa API REST para los widgets SQL preview, sin depender de que el SDK estable represente esos campos. `observability/schema/` contiene su esquema oficial; `scripts/validate_dashboard.py` lo verifica localmente. Las consultas deben confirmarse contra el esquema ingerido del proyecto.

**Continúa con [pasos_gcp.md](docs/pasos_gcp.md)** para configurar proyecto y ADC, revisar/aplicar el plan, verificar señales antes de la hora, ejecutar tráfico, guardar dashboard/capturas y destruir recursos. No ejecutes la configuración oficial hasta sustituir su URL y comprobar las métricas.

## Evidencia y análisis

`evidence/local-dry-run/`: plan real de 6000 eventos, cero envíos. `evidence/local-smoke/`: 60 solicitudes HTTP locales, resumen, preparación y logs correlacionados. `evidence/local-contract/`: contrato HTTP y evidencia de 500. Estas son pruebas locales, no resultados de GCP.

```bash
.venv/bin/python scripts/analyze.py evidence/local-smoke \
  --logs evidence/local-smoke/logs_sample.jsonl
```

Produce `analysis.json` y `analysis.md`, con tasas por categoría/ventana, intenciones, latencias cliente/backend, retrasos y correlación. [analisis.md](docs/analisis.md) interpreta la evidencia disponible y distingue lo pendiente. Nunca se incluyen credenciales ni archivos Terraform state en el repositorio; conserva tu estado local para poder destruir únicamente los recursos administrados.
