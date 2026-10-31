# Análisis de local-smoke

Ejecución: **accelerated_test**, estado **complete**.

La evidencia local/acelerada no demuestra una hora real ni ingestión en GCP.

Ventana de envío: 2026-10-31T01:05:09.492136+00:00 a 2026-10-31T01:05:16.692136+00:00; fin del drenado: 2026-10-31T01:05:16.693745+00:00.

Intentos: 60. Clases HTTP y transporte: `{'2xx': 37, '4xx': 23}`.

## Volumen

Conteos por minuto programado: `{10: 1, 15: 1, 16: 1, 19: 1, 20: 1, 21: 6, 23: 3, 24: 1, 25: 3, 26: 3, 27: 1, 28: 3, 29: 2, 30: 2, 31: 2, 32: 4, 33: 3, 34: 3, 35: 2, 36: 4, 37: 3, 38: 3, 39: 2, 41: 2, 42: 1, 44: 1, 51: 1}`.

Comparar la concentración cerca del minuto 30 con traffic_by_minute.sql y la métrica nativa; el CSV clasifica por envío programado, el backend registra finalización.

## Escenario y errores

Ventana de comparación [35,45) para todas las categorías. Solo electronics tiene double_errors en la configuración oficial. Tasas HTTP usan respuestas como denominador; intención usa intentos.

| Categoría | Ventana | n intentos | n respuestas | Inválidas planeadas | 4xx | Tasa 4xx |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| books | baseline | 13 | 13 | 6 | 6 | 46.15% |
| books | scenario_window | 7 | 7 | 1 | 1 | 14.29% |
| clothing | baseline | 12 | 12 | 2 | 2 | 16.67% |
| clothing | scenario_window | 6 | 6 | 3 | 3 | 50.00% |
| electronics | baseline | 17 | 17 | 8 | 8 | 47.06% |
| electronics | scenario_window | 5 | 5 | 3 | 3 | 60.00% |

No exigir exactamente el doble ni frecuencias exactas en una muestra. El escenario modifica probabilidad de errores de cliente; FAILURE_RATE se aplica a operaciones válidas.

## Latencia y correlación

Cliente por operación/segmento: `{'cancel / premium': {'p50': 25.681, 'p95': 31.86}, 'cancel / standard': {'p50': 21.326, 'p95': 34.9}, 'create / premium': {'p50': 21.849, 'p95': 22.469}, 'create / standard': {'p50': 22.337, 'p95': 24.27}, 'get / premium': {'p50': 21.529, 'p95': 24.139}, 'get / standard': {'p50': 21.204, 'p95': 21.503}}`.

Backend por endpoint/segmento: `{'GET /orders/{id} / premium': {'p50': 18.87, 'p95': 20.965}, 'GET /orders/{id} / standard': {'p50': 18.709, 'p95': 19.248}, 'POST /orders / premium': {'p50': 19.409, 'p95': 20.187}, 'POST /orders / standard': {'p50': 19.892, 'p95': 21.964}, 'POST /orders/{id}/cancel / premium': {'p50': 23.323, 'p95': 29.586}, 'POST /orders/{id}/cancel / standard': {'p50': 18.52, 'p95': 32.278}}`.

Retraso de despacho en ms: `{'p50': 0.842, 'p95': 1.831}`. La latencia cliente incluye red, pool y autenticación; backend incluye Firestore y demora artificial.

Logs: `{'provided': True, 'events_for_run': 60, 'paired_requests': 60, 'duplicate_ids': 0, 'status_mismatches': [], 'error_types': {'not_found': 8, 'invalid_state': 7, 'invalid_payload': 8}}`.

Para investigar una fila, copiar su request_id en correlate_request.sql o filtrar jsonPayload.request_id en Logs Explorer. Un timeout no demuestra que el backend no haya escrito.

## Validación de nube pendiente

Confirmar los descriptores y resultados en el dashboard, esperar ingestión, exportar JSON y captura. Las métricas incluyen preparación si se amplía la ventana; SQL excluye phase=preparation. No hay datos de métricas nativas disponibles en este informe de archivos.
