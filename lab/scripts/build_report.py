"""Genera el informe Markdown de la raíz a partir de evidencias oficiales guardadas."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "lab"
RUN = "official-20261031T025905Z"
DIR = LAB / "evidence" / RUN
REL = f"lab/evidence/{RUN}"


def read(name):
    return json.loads((DIR / name).read_text())


def build():
    summary, analysis, detail = (
        read("summary.json"),
        read("analysis.json"),
        read("report-data.json"),
    )
    reconciliation = read("monitoring/reconciliation.json")
    source = read("source-manifest.json")
    spec = json.loads((LAB / "reports/report-spec.json").read_text())
    with (DIR / "requests.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert summary["status"] == "complete" and summary["time_scale"] == 1
    assert len(rows) == len({row["request_id"] for row in rows}) == 6000
    assert analysis["logs"]["paired_requests"] == 6000
    assert reconciliation["all_dashboard_sql_use_official_run"]

    statuses = []
    for code, meaning in [
        (201, "Pedido creado"),
        (200, "Consulta o cancelación correcta"),
        (400, "Payload inválido"),
        (404, "Pedido inexistente"),
        (409, "Estado incompatible"),
        (500, "Falla simulada"),
    ]:
        count = summary["http_status_codes"][str(code)]
        statuses.append(f"| {code} | {meaning} | {count} | {count / 6000:.2%} |")
    scenario_rows = []
    for category in ["books", "clothing", "electronics"]:
        base = next(
            item
            for item in analysis["category_rates"]
            if item["category"] == category and item["period"] == "baseline"
        )
        inside = next(
            item
            for item in analysis["category_rates"]
            if item["category"] == category and item["period"] == "scenario_window"
        )
        scenario_rows.append(
            f"| {category} | {base['client_errors']}/{base['attempts']} = {base['client_error_rate_http']:.2%} "
            f"| {inside['client_errors']}/{inside['attempts']} = {inside['client_error_rate_http']:.2%} "
            f"| {(inside['client_error_rate_http'] - base['client_error_rate_http']) * 100:+.2f} |"
        )
    latency_rows = []
    for operation, endpoint, label in [
        ("create", "POST /orders", "Crear"),
        ("get", "GET /orders/{id}", "Consultar"),
        ("cancel", "POST /orders/{id}/cancel", "Cancelar"),
    ]:
        for tier in ["standard", "premium"]:
            client = analysis["client_latency_by_operation_tier"][f"{operation} / {tier}"]
            backend = analysis["backend_latency_by_endpoint_tier"][f"{endpoint} / {tier}"]
            latency_rows.append(
                f"| {label} | {tier} | {client['p50']:.3f} | {client['p95']:.3f} "
                f"| {backend['p50']:.3f} | {backend['p95']:.3f} |"
            )
    sample = detail["correlation_example_csv"]
    event = detail["correlation_example_log"]["jsonPayload"]
    sample_json = json.dumps(
        {
            key: event[key]
            for key in [
                "request_id",
                "run_id",
                "endpoint",
                "status_code",
                "outcome",
                "error_type",
                "category",
                "customer_tier",
                "amount",
                "latency_ms",
            ]
        },
        ensure_ascii=False,
        indent=2,
    )
    examples = "\n".join(
        f"| {code} | `{detail['http_examples'][str(code)]['request_id'].split('-request-')[1]}` "
        f"| `{detail['http_examples'][str(code)]['intended_event']}` |"
        for code in [201, 200, 400, 404, 409, 500]
    )
    text = f"""# {spec["header"]}

**Laboratorio: API serverless observable en GCP**

Repositorio: [{spec["repository"]}]({spec["repository"]})

Se implementó una API de pedidos en Python, se desplegó mediante Terraform en Cloud Run functions de segunda generación y se ejecutó una hora real de tráfico concurrente. La corrida completó **6000 intentos, 6000 respuestas HTTP y 6000 logs de aplicación correlacionados**, sin errores de transporte. El dashboard integra métricas nativas, métricas basadas en logs, consultas SQL y un panel de logs.

**Estado:** implementación, despliegue, observabilidad y corrida oficial verificados. **La destrucción de los recursos de GCP sigue pendiente**; no se presenta como realizada.

La [guía de ejecución](lab/README.md) contiene instalación, emulador, pruebas y comandos completos.

## Implementación y despliegue

La función HTTP se llama `handle`. Los pedidos se guardan en una base Firestore nativa dedicada, `lab-orders`, dentro de colecciones separadas por `run_id`. Las operaciones son:

| Método y ruta | Operación | Resultado funcional |
| --- | --- | --- |
| `POST /orders` | Crear | 201; estado `created` |
| `GET /orders/{{id}}` | Consultar | 200; pedido persistido |
| `POST /orders/{{id}}/cancel` | Cancelar | 200; transición a `cancelled` |

Se validan categoría, segmento y monto finito positivo; los booleanos no se aceptan como montos. Se devuelve 400 ante payload inválido, 404 ante recurso inexistente y 409 al cancelar un pedido ya cancelado. Rutas desconocidas y métodos incorrectos producen 404 y 405, respectivamente. La cancelación vuelve a comprobar el estado dentro de una transacción de Firestore para impedir dos transiciones concurrentes del mismo pedido.

`FAILURE_RATE=0.02` inyecta fallas 500 después de validar y antes de escribir. Los errores de cliente mantienen su código. `EXTRA_LATENCY_MS=0` en la corrida oficial; la demora adicional se probó por separado. Cada solicitud atendida emite un evento JSON `request_completed` con ID, endpoint normalizado, código, resultado, tipo de error, latencia y atributos de negocio. El ID se propaga mediante `X-Request-ID` y aparece en el CSV y en los logs.

| Configuración de infraestructura | Valor utilizado |
| --- | --- |
| Proyecto / región | `adfasdfasfd-1899a` / `us-central1` |
| Función / runtime / entrada | `orders-api` / `python313` / `handle` |
| Memoria / CPU / timeout | 512 MiB / 1 CPU / 60 s |
| Escalado / concurrencia por instancia | 0–10 instancias / 1 solicitud |
| Persistencia | Firestore nativo, base dedicada `lab-orders` |
| Identidades | Cuentas de servicio distintas para build y ejecución |
| Fuentes e imágenes | ZIP con hash en Storage y repositorio propio de Artifact Registry |
| Logs | `_Default` global, 30 días de retención y Analytics habilitado |

La infraestructura también configura APIs, permisos, dos métricas basadas en logs y el dashboard. El primer build falló por acceso al bucket de staging; se comprobó que `storage.objectViewer` ya estaba asignado y el reintento, después de esperar propagación, terminó correctamente. Esa propagación es la explicación probable; no se otorgaron roles adicionales a ciegas.

- [Función desplegada](https://orders-api-gfr6cqd5yq-uc.a.run.app).
- [Dashboard único de Monitoring](https://console.cloud.google.com/monitoring/dashboards/builder/9e847e3b-cd26-45f6-9cdf-de9c34ffbf93?project=adfasdfasfd-1899a).
- Vista SQL: `adfasdfasfd-1899a.global._Default._Default`.
- [Terraform](lab/infra), [backend](lab/backend) y [simulador](lab/simulator/simulator.py).

Los enlaces al servicio y dashboard dependen de que esos recursos sigan activos; la evidencia del repositorio se conserva después del cierre.

## Configuración y ejecución del experimento

| Parámetro | Configuración o resultado comprobado |
| --- | --- |
| Corrida | `{RUN}` |
| Solicitudes / semilla | 6000 / 42 |
| Distribución | Normal con μ=30 min y σ=10 min, truncada por rechazo a [0,60] |
| Probabilidad base de inválidas | 0.08 |
| Escenario | `double_errors` en `electronics`, minutos [35,45): 0.08 → 0.16 |
| Inicio UTC | 31/10/2026 03:01:22.409460 |
| Fin de la ventana UTC | 31/10/2026 04:01:22.409460 |
| Fin del proceso UTC | 31/10/2026 04:01:22.415622 |
| Hora de Guatemala, UTC−6 | 30/10/2026, 21:01:22–22:01:22 |
| Duración / escala | {summary["elapsed_s"]:.6f} s / 1.0 |
| Programadas / enviadas / completadas | 6000 / 6000 / 6000 |
| Respuestas / errores de transporte | 6000 / 0 |

El simulador usa un generador NumPy con semilla fija, remuestrea los valores fuera de la hora y guarda el calendario antes del tráfico. HTTPX y `asyncio` despachan tareas independientes mediante reloj monotónico, sin esperar la respuesta anterior ni reintentar el tráfico medido.

La preparación confirmó **1119 pedidos**, mediante **1154 intentos HTTP**: 1119 creaciones, 6 cancelaciones y 29 fallas artificiales con sus reintentos. Se ejecutó fuera del CSV medido, con `phase=preparation`, y después hubo 120 s de quietud. Las consultas reutilizan pedidos preparados; cada cancelación válida tiene un pedido reservado. La laptop ejecutó la corrida con bloqueo de suspensión.

La mezcla final fue de 2879 creaciones, 1744 consultas y 1377 cancelaciones. Puede variar respecto a la mezcla base 50/30/20 porque los eventos inválidos ajustan la operación para provocar 400, 404 o 409.

Versiones verificadas: Python 3.13.15, Functions Framework 3.10.2, Firestore SDK 2.34.1, NumPy 2.5.4, HTTPX 0.28.1, Terraform 1.13.5, proveedor Google 6.50.0 y archive 2.8.1. El [manifiesto previo](lab/evidence/{RUN}/source-manifest.json) registra el commit de referencia `{source["git_commit"][:7]}` y las huellas SHA-256 de los archivos efectivos, incluidos los cambios que aún no tenían commit al tomar esa instantánea.

## Resultados de la hora oficial

### Volumen y distribución temporal

Los 6000 instantes programados tuvieron media **{detail["scheduled_mean_min"]:.3f} min** y desviación estándar **{detail["scheduled_std_min"]:.3f} min**. La mayor frecuencia fue **274 solicitudes en [33,34) min**. La concentración alrededor del minuto 30 concuerda con el diseño normal truncado; el máximo de una muestra no tiene que ocurrir exactamente en μ.

![Distribución temporal de los 6000 intentos oficiales]({REL}/figures/trafico_oficial.png)

La figura se reconstruye desde el CSV oficial, excluye preparación y separa los códigos observados. La línea discontinua muestra el conteo esperado de la distribución configurada; la franja marca [35,45). Las métricas de GCP usan intervalos de calendario y tiempos del servidor, por lo que sus barras no tienen exactamente el mismo origen que los minutos programados del simulador.

### Códigos HTTP e intención del simulador

| Código | Interpretación | Respuestas | Proporción de 6000 |
| --- | --- | ---: | ---: |
{chr(10).join(statuses)}
| **Total** | | **6000** | **100.00 %** |

Agrupando por clase: **5360 éxitos (89.33 %)**, **526 errores de cliente (8.77 %)** y **114 errores de servidor (1.90 %)**. Los 526 eventos inválidos planificados coinciden con 161 respuestas 400, 181 respuestas 404 y 184 respuestas 409. Los 114 eventos 500 fueron `simulated_failure`; no hubo `internal_error` en los logs oficiales.

Se planificaron 5474 operaciones funcionalmente válidas. La inyección se aplica a ese conjunto: 114/5474 = **{114 / 5474:.2%}**, cercano al parámetro de 2 %. El 1.90 % usa como denominador todos los intentos, incluidas las solicitudes inválidas que conservan sus errores de cliente. Esta distinción evita atribuir todas las fallas observadas a la generación de payloads inválidos.

### Escenario de errores por categoría

La ventana [35,45) corresponde aproximadamente a **21:36:22–21:46:22, UTC−6**. Se clasifica por el instante programado para conservar la reproducibilidad. El escenario duplica la probabilidad de una solicitud inválida de `electronics`; no modifica `FAILURE_RATE`.

| Categoría | Fuera de [35,45): 4xx/total y tasa | Dentro de [35,45): 4xx/total y tasa | Cambio, puntos porcentuales |
| --- | --- | --- | ---: |
{chr(10).join(scenario_rows)}

![Comparación de tasas de errores de cliente por categoría]({REL}/figures/errores_por_categoria.png)

En `electronics`, la tasa creció de **8.10 % a 15.47 %**, aproximadamente **1.91 veces**, consistente con la probabilidad configurada de 0.08 → 0.16. No se exige una duplicación exacta de frecuencias. Los denominadores también cambian porque la llegada de solicitudes sigue una distribución normal.

`books` permaneció cerca de su línea base; `clothing` también aumentó de 7.35 % a 12.24 %, aunque no tenía un efecto programado. Por ello se muestran los tamaños de muestra y las categorías de comparación: una sola corrida con semilla fija permite describir lo ocurrido, pero no aislar causalmente cualquier pico ni demostrar una frecuencia exacta para todos los grupos.

### Latencia del cliente, del backend y retraso de despacho

| Medición sobre la corrida completa | p50, ms | p95, ms | p99, ms |
| --- | ---: | ---: | ---: |
| Cliente | 110.312 | 248.941 | 554.284 |
| Backend, logs de aplicación | 16.855 | 57.829 | 110.558 |
| Retraso de despacho | 0.860 | 1.954 | 2.393 |

| Operación | Segmento | Cliente p50, ms | Cliente p95, ms | Backend p50, ms | Backend p95, ms |
| --- | --- | ---: | ---: | ---: | ---: |
{chr(10).join(latency_rows)}

![Comparación de latencia p95 por operación y segmento]({REL}/figures/latencia_p95.png)

Las cancelaciones tuvieron mayor latencia de backend; su implementación comprueba el estado y ejecuta una actualización transaccional. La latencia cliente incluye red y posibles esperas del pool, mientras que la aplicación mide su manejador y Firestore. La métrica nativa mide otra frontera del servicio. Estas mediciones no son intercambiables.

El máximo de latencia cliente fue **{detail["max_client_latency_ms"]:.3f} ms**. Hubo **4 despachos con retraso superior a 100 ms**, de los cuales 2 superaron 1 s; el máximo fue **{detail["max_dispatch_delay_ms"]:.3f} ms**. Se conservaron esas desviaciones y los 6000 envíos permanecieron dentro de la ventana. No se registró telemetría local suficiente para atribuir esos retrasos a una causa específica.

Los percentiles de esta tabla se calcularon sobre las muestras individuales del CSV y los logs, incluyendo éxitos y errores. Los widgets calculan percentiles por minuto, operación y segmento; SQL usa `APPROX_QUANTILES` y las métricas de distribución dependen de sus buckets. No se promedian los percentiles de las instancias para obtener un percentil global.

### Correlación de una solicitud

La captura de logs muestra la solicitud **`{sample["request_id"]}`**, una consulta de `books` para un cliente `premium`. En el CSV su intención era válida y esperaba 200, pero recibió 500. El evento correlacionado identifica una falla artificial:

```json
{sample_json}
```

El intento comenzó a las **03:45:09.051614 UTC**, con retraso de despacho de **{float(sample["dispatch_delay_ms"]):.3f} ms**. El cliente midió **{float(sample["client_latency_ms"]):.3f} ms** y el backend **{event["latency_ms"]:.3f} ms**. El ID coincide en ambos archivos. El estado HTTP 500 se comprueba en el CSV y el evento exportado, aunque queda fuera del recorte inferior de la captura.

Para los seis códigos observados se conservaron, entre otros, estos ejemplos. Todos usan el prefijo `{RUN}-request-`:

| HTTP | Sufijo del request_id | Intención |
| --- | --- | --- |
{examples}

El cruce completo obtuvo **6000 IDs únicos, 6000 logs, cero duplicados y cero diferencias de código**. Los logs registraron actividad de **9 instancias**. La preparación se excluye mediante fase y ventana; el [CSV](lab/evidence/{RUN}/requests.csv) y los [logs JSONL](lab/evidence/{RUN}/logs_sample.jsonl) permiten reproducir la correlación.

## Dashboard único y contraste de fuentes

El [JSON final exportado](lab/evidence/{RUN}/dashboard.json) conserva los cambios hechos por consola. Sus tres consultas SQL, incluida la gráfica adicional de errores verificada durante el smoke, apuntan a `{RUN}`. Las métricas de logs se crearon a las **02:02:58/59 UTC**, antes de la preparación y la corrida oficiales, según los [descriptores iniciales](lab/evidence/gcp-setup).

Las consultas SQL filtran proyecto/vista, servicio, `run_id`, `phase=traffic` e inicio/fin UTC. El widget de latencia usa una medida numérica y una etiqueta de serie que combina segmento, operación y percentil; así muestra p50 y p95 con desglose. Los filtros del dashboard no reemplazan los filtros propios del SQL.

| Fuente | Señal de volumen o muestra | Resultado oficial |
| --- | --- | ---: |
| CSV del simulador | Intentos con ID único | 6000 |
| Logs de aplicación | Eventos request_completed correlacionados | 6000 |
| Métrica nativa | run.googleapis.com/request_count | 6000 |
| Métrica de logs | lab_request_completed_count | 6000 |
| Distribución de logs | Muestras de lab_request_latency_ms | 6000 |
| Distribución nativa | Muestras de run.googleapis.com/request_latencies | 6006 |

La exportación de Monitoring usa **03:01–04:02 UTC** para incluir bins completos de 60 s que contienen la hora medida; el CSV y los logs mantienen los límites exactos. En ese intervalo, ambos contadores coinciden también por clase: 5360 éxitos, 526 errores de cliente y 114 de servidor.

La distribución nativa de latencia reportó **6006 muestras**, una diferencia de 6 (+0.10 %) frente a los contadores. Se conserva ese dato y no se interpreta como seis intentos adicionales del simulador. Con las señales agregadas disponibles no se aisló la causa; esa métrica no permite emparejar sus muestras por request_id. Las conclusiones de volumen usan el contador y la correlación CSV/logs, y los percentiles globales del backend usan los 6000 eventos individuales. Los [datos de Monitoring](lab/evidence/{RUN}/monitoring) y la [conciliación](lab/evidence/{RUN}/monitoring/reconciliation.json) conservan esa diferencia.

### Métricas nativas

![Solicitudes y latencia nativas de Cloud Run]({REL}/captures/01_metricas_nativas.png)

### Métricas basadas en logs

![Resultados por categoría y latencia por operación y segmento]({REL}/captures/02_metricas_logs.png)

En las dos capturas anteriores se ve un pico al borde izquierdo que incluye la preparación. La exportación separada del intervalo previo confirmó **1154 solicitudes preparatorias: 1125 éxitos y 29 fallas simuladas**. No forman parte de los 6000 intentos oficiales. Las figuras reconstruidas, tablas y contadores conciliados de este informe excluyen ese intervalo. Las capturas se conservan como evidencia visual original, sin borrar ni corregir ese pico.

### Gráficas SQL de Analytics

![Tasa de errores y latencia SQL de la corrida oficial]({REL}/captures/03_sql.png)

Los picos de tasa en minutos con pocos eventos deben leerse junto con su denominador; por ejemplo, una sola respuesta de error puede dar 100 % en una categoría con una sola solicitud. El análisis del escenario usa las ventanas completas y sus tamaños de muestra, no el máximo de un minuto aislado.

### Panel de logs y solicitud correlacionada

![Evento de la solicitud oficial 005514 expandido en el panel de logs]({REL}/captures/04_logs_correlacion.png)

Las imágenes fueron proporcionadas por el usuario. Los recortes no muestran el selector global de fecha; por eso el alcance del reporte se verifica adicionalmente con summary.json, el calendario, los logs exportados y los filtros del dashboard guardado.

## Verificación, reproducibilidad y cierre

Antes del despliegue se aprobaron **60 pruebas locales**, incluida persistencia entre clientes/procesos y cancelación concurrente contra el emulador oficial de Firestore. Se aprobaron formato/validación Terraform y **4 pruebas con Google simulado**; estas últimas no se presentan como un despliegue real. Posteriormente se aprobaron **5 pruebas de observabilidad**, incluyendo compatibilidad de configuración y migración del widget SQL. El despliegue, la prueba contractual, los smoke tests y la hora oficial aportan la evidencia de GCP descrita en este reporte.

Los [archivos de avance](lab/docs/avance.md), [ejecución](lab/docs/ejecucion.md) y [decisiones](lab/docs/decisiones.md) registran el proceso. Para reproducir los cálculos y las figuras, desde la raíz y con las dependencias instaladas:

```bash
lab/.venv/bin/python lab/scripts/analyze.py \\
  lab/evidence/{RUN} \\
  --logs lab/evidence/{RUN}/logs_sample.jsonl

# Instalar requirements-report.txt en el entorno usado para generar figuras.
python lab/scripts/plot_report.py lab/evidence/{RUN}

python lab/scripts/build_report.py
```

El último comando reconstruye este README desde las evidencias guardadas. La exportación adicional es de solo lectura y usa el [API de series de Monitoring](https://docs.cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.timeSeries/list); los tokens se mantienen en memoria. Las capturas originales se incluyen como archivos y el resto de las figuras se genera desde datos, con Matplotlib.

**Cierre pendiente:** no se ha verificado `terraform destroy` ni la ausencia de residuos. Después de preservar y revisar los resultados debe revisarse el plan de destrucción y eliminar únicamente los recursos propios del laboratorio, incluida `lab-orders`; la base preexistente `(default)` queda fuera de ese alcance. Las APIs configuradas con `disable_on_destroy=false`, la habilitación permanente de Analytics y el bucket automático de logs pueden permanecer. El estado final y los residuos deberán registrarse cuando la limpieza se ejecute.

### Evidencias principales

- [Configuración](lab/evidence/{RUN}/config.json), [calendario](lab/evidence/{RUN}/schedule.csv), [CSV](lab/evidence/{RUN}/requests.csv) y [resumen final](lab/evidence/{RUN}/summary.json).
- [Preparación](lab/evidence/{RUN}/preparation_summary.json), [manifiesto de fuentes](lab/evidence/{RUN}/source-manifest.json) y [análisis numérico](lab/evidence/{RUN}/analysis.json).
- [Logs de aplicación](lab/evidence/{RUN}/logs_sample.jsonl), [series y descriptores de Monitoring](lab/evidence/{RUN}/monitoring) y [dashboard final](lab/evidence/{RUN}/dashboard.json).
- [SQL ejecutable con filtros oficiales](lab/evidence/{RUN}/rendered), [capturas](lab/evidence/{RUN}/captures) y [figuras reproducibles](lab/evidence/{RUN}/figures).
"""
    (ROOT / "README.md").write_text(text, encoding="utf-8")
    print(f"Reporte generado en {ROOT / 'README.md'}")


if __name__ == "__main__":
    build()
