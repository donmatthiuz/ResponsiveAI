# Análisis de smoke-20261031T020723Z

Ejecución: **accelerated_test**, estado **complete**.

La evidencia local/acelerada no demuestra una hora real ni ingestión en GCP.

Ventana de envío: 2026-10-31T02:07:27.947662+00:00 a 2026-10-31T02:07:35.147662+00:00; fin del drenado: 2026-10-31T02:07:35.148179+00:00.

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

Cliente por operación/segmento: `{'cancel / premium': {'p50': 145.365, 'p95': 185.195}, 'cancel / standard': {'p50': 152.573, 'p95': 232.487}, 'create / premium': {'p50': 127.009, 'p95': 161.199}, 'create / standard': {'p50': 138.917, 'p95': 257.668}, 'get / premium': {'p50': 119.21, 'p95': 134.91}, 'get / standard': {'p50': 136.62, 'p95': 147.595}}`.

Backend por endpoint/segmento: `{'GET /orders/{id} / premium': {'p50': 11.426, 'p95': 31.581}, 'GET /orders/{id} / standard': {'p50': 19.459, 'p95': 36.658}, 'POST /orders / premium': {'p50': 26.002, 'p95': 48.562}, 'POST /orders / standard': {'p50': 21.739, 'p95': 171.498}, 'POST /orders/{id}/cancel / premium': {'p50': 53.573, 'p95': 82.325}, 'POST /orders/{id}/cancel / standard': {'p50': 40.77, 'p95': 120.726}}`.

Retraso de despacho en ms: `{'p50': 0.767, 'p95': 1.426}`. La latencia cliente incluye red, pool y autenticación; backend incluye Firestore y demora artificial.

Logs: `{'provided': True, 'events_for_run': 60, 'paired_requests': 60, 'duplicate_ids': 0, 'status_mismatches': [], 'error_types': {'not_found': 8, 'invalid_state': 7, 'invalid_payload': 8}}`.

Para investigar una fila, copiar su request_id en correlate_request.sql o filtrar jsonPayload.request_id en Logs Explorer. Un timeout no demuestra que el backend no haya escrito.

## Validación de nube pendiente

Confirmar los descriptores y resultados en el dashboard, esperar ingestión, exportar JSON y captura. Las métricas incluyen preparación si se amplía la ventana; SQL excluye phase=preparation. No hay datos de métricas nativas disponibles en este informe de archivos.
