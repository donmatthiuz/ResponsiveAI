# Análisis de official-20261031T025905Z

Ejecución: **one_hour_execution**, estado **complete**.

La evidencia local/acelerada no demuestra una hora real ni ingestión en GCP.

Ventana de envío: 2026-10-31T03:01:22.409460+00:00 a 2026-10-31T04:01:22.409460+00:00; fin del drenado: 2026-10-31T04:01:22.415622+00:00.

Intentos: 6000. Clases HTTP y transporte: `{'4xx': 526, '2xx': 5360, '5xx': 114}`.

## Volumen

Conteos por minuto programado: `{0: 5, 1: 4, 2: 10, 3: 8, 4: 6, 5: 10, 6: 19, 7: 20, 8: 28, 9: 24, 10: 34, 11: 56, 12: 59, 13: 57, 14: 77, 15: 90, 16: 99, 17: 87, 18: 115, 19: 150, 20: 155, 21: 170, 22: 174, 23: 208, 24: 174, 25: 208, 26: 227, 27: 224, 28: 222, 29: 256, 30: 263, 31: 216, 32: 248, 33: 274, 34: 231, 35: 207, 36: 180, 37: 197, 38: 166, 39: 133, 40: 127, 41: 128, 42: 95, 43: 86, 44: 94, 45: 61, 46: 59, 47: 53, 48: 39, 49: 42, 50: 28, 51: 14, 52: 21, 53: 14, 54: 16, 55: 10, 56: 4, 57: 7, 58: 7, 59: 4}`.

Comparar la concentración cerca del minuto 30 con traffic_by_minute.sql y la métrica nativa; el CSV clasifica por envío programado, el backend registra finalización.

## Escenario y errores

Ventana de comparación [35,45) para todas las categorías. Solo electronics tiene double_errors en la configuración oficial. Tasas HTTP usan respuestas como denominador; intención usa intentos.

| Categoría | Ventana | n intentos | n respuestas | Inválidas planeadas | 4xx | Tasa 4xx |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| books | baseline | 1495 | 1495 | 124 | 124 | 8.29% |
| books | scenario_window | 521 | 521 | 39 | 39 | 7.49% |
| clothing | baseline | 1537 | 1537 | 113 | 113 | 7.35% |
| clothing | scenario_window | 433 | 433 | 53 | 53 | 12.24% |
| electronics | baseline | 1555 | 1555 | 126 | 126 | 8.10% |
| electronics | scenario_window | 459 | 459 | 71 | 71 | 15.47% |

No exigir exactamente el doble ni frecuencias exactas en una muestra. El escenario modifica probabilidad de errores de cliente; FAILURE_RATE se aplica a operaciones válidas.

## Latencia y correlación

Cliente por operación/segmento: `{'cancel / premium': {'p50': 130.39, 'p95': 271.413}, 'cancel / standard': {'p50': 131.678, 'p95': 276.171}, 'create / premium': {'p50': 103.131, 'p95': 246.229}, 'create / standard': {'p50': 103.58, 'p95': 239.933}, 'get / premium': {'p50': 96.603, 'p95': 232.323}, 'get / standard': {'p50': 96.536, 'p95': 225.365}}`.

Backend por endpoint/segmento: `{'GET /orders/{id} / premium': {'p50': 9.038, 'p95': 22.473}, 'GET /orders/{id} / standard': {'p50': 8.899, 'p95': 25.125}, 'POST /orders / premium': {'p50': 17.82, 'p95': 36.318}, 'POST /orders / standard': {'p50': 17.675, 'p95': 38.259}, 'POST /orders/{id}/cancel / premium': {'p50': 41.292, 'p95': 90.271}, 'POST /orders/{id}/cancel / standard': {'p50': 41.904, 'p95': 102.709}}`.

Retraso de despacho en ms: `{'p50': 0.86, 'p95': 1.954}`. La latencia cliente incluye red, pool y autenticación; backend incluye Firestore y demora artificial.

Logs: `{'provided': True, 'events_for_run': 6000, 'paired_requests': 6000, 'duplicate_ids': 0, 'status_mismatches': [], 'error_types': {'invalid_state': 184, 'simulated_failure': 114, 'not_found': 181, 'invalid_payload': 161}}`.

Para investigar una fila, copiar su request_id en correlate_request.sql o filtrar jsonPayload.request_id en Logs Explorer. Un timeout no demuestra que el backend no haya escrito.

## Validación de nube pendiente

Confirmar los descriptores y resultados en el dashboard, esperar ingestión, exportar JSON y captura. Las métricas incluyen preparación si se amplía la ventana; SQL excluye phase=preparation. No hay datos de métricas nativas disponibles en este informe de archivos.
