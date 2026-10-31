# Análisis de la evidencia disponible

**Alcance: pruebas locales y smoke acelerado en GCP; hora oficial pendiente.** El informe local detallado es [local-smoke/analysis.md](../evidence/local-smoke/analysis.md). El informe del smoke remoto está en [smoke-20261031T020723Z/analysis.md](../evidence/smoke-20261031T020723Z/analysis.md). Los apartados 1–5 siguientes conservan el análisis local original; esta actualización incorpora además resultados de GCP comprobados.

## Avance con datos reales de GCP

`smoke-20261031T020723Z` envió y completó 60 intentos en 7.2 s: 37 éxitos, 23 errores de cliente y ningún error de transporte. Se exportaron 60 logs y se emparejaron 60 IDs sin duplicados ni diferencias de código. La latencia cliente fue p50=134.949 ms y p95=232.443 ms; despacho p50=0.767 ms y p95=1.426 ms. El backend usa EXTRA_LATENCY_MS=0 en GCP; no se deben comparar esos números como si tuvieran la misma configuración que el smoke local de 15 ms.

La consulta SQL de errores devuelve books:7/20=35 %, clothing:5/18=27.78 % y electronics:11/22=50 %. El usuario confirmó esos tres puntos en una gráfica manual guardada en el dashboard. Las métricas nativas, las de logs y el panel de logs también muestran tráfico. La configuración de los dos SQL originales se está ajustando según esa gráfica; el panel de latencia SQL todavía requiere validación visual. Se exportó el JSON real antes de preparar cambios.

La prueba contractual previa `check-20261031T020537Z` registró 54 intentos y un 500 `simulated_failure`, ID `check-20261031T020537Z-check-0053`, con log correlacionado en `500-log.json`. Ninguno de estos resultados acredita una hora real de 6000 solicitudes.

## 1. ¿El volumen se concentra cerca del minuto 30?

El dry-run oficial produjo exactamente 6000 instantes entre 8.506 s y 3597.743 s, con media 29.906 min. Esto verifica el generador/calendario, no la distribución del tráfico atendido por una función en GCP. El smoke de 60 instantes es demasiado pequeño y acelerado para sustituir esa medición. La comprobación pendiente compara el CSV de la hora real con `traffic_by_minute.sql` y solicitudes/minuto de Cloud Run, usando la misma ventana.

## 2. ¿Qué proporción termina en 2xx, 4xx y 5xx?

En `local-smoke`: 37/60 (61.67 %) fueron 2xx, 23/60 (38.33 %) 4xx y 0/60 5xx. Se usó `invalid_share=0.30`, no 0.08, para ejercitar errores con pocas solicitudes. Hubo 8 payloads inválidos, 8 IDs inexistentes y 7 cancelaciones imposibles; sus códigos observados coincidieron con la intención. No hubo errores de transporte.

La prueba contractual adicional observó un 500 `simulated_failure`, ID `local-contract-check-0010`, antes de escribir un pedido. Las pruebas automatizadas también comprueban tasa 1 y ausencia de modificaciones, y distinguen `internal_error` de `simulated_failure`. La ausencia de 500 en 60 intentos no contradice la tasa configurada: la muestra es pequeña y la inyección solo se aplica tras validar.

## 3. ¿Aumentó la tasa de errores de electronics entre 35 y 45?

La lógica fue probada en los límites exactos [35,45), usando valores de configuración y tope 1. En el plan oficial: fuera del escenario la probabilidad es 0.08; dentro para electronics es 0.16. Eso no exige frecuencias observadas idénticas.

| Categoría | Fuera de [35,45), errores/total | Dentro de [35,45), errores/total |
| --- | --- | --- |
| electronics | 8/17 = 47.06 % | 3/5 = 60.00 % |
| books | 6/13 = 46.15 % | 1/7 = 14.29 % |
| clothing | 2/12 = 16.67 % | 3/6 = 50.00 % |

Son resultados del smoke con base 0.30 y escenario 0.60. Las muestras de 5–17 eventos por grupo no acreditan un efecto estadístico; se conserva el denominador para evitar confundir volumen con probabilidad. La corrida oficial deberá comparar tasas y tamaños de muestra por categoría y ventana. El CSV agrupa según minuto programado; Analytics registra finalización, que puede cruzar los bordes por retraso/latencia.

## 4. ¿Cómo varían p50/p95 por operación y segmento?

En el smoke, con demora artificial 15 ms:

| Operación / segmento | Cliente p50 / p95, ms | Backend p50 / p95, ms |
| --- | --- | --- |
| Crear / premium | 21.849 / 22.469 | 19.409 / 20.187 |
| Crear / standard | 22.337 / 24.270 | 19.892 / 21.964 |
| Consultar / premium | 21.529 / 24.139 | 18.870 / 20.965 |
| Consultar / standard | 21.204 / 21.503 | 18.709 / 19.248 |
| Cancelar / premium | 25.681 / 31.860 | 23.323 / 29.586 |
| Cancelar / standard | 21.326 / 34.900 | 18.520 / 32.278 |

Se incluyen éxitos y errores de cada operación, por lo que la composición también afecta esos percentiles. El cliente incluye red/pool y, cuando aplica, autenticación; el backend mide acceso a Firestore y demora artificial. El retraso de despacho es otra variable: p50 0.842 ms y p95 1.831 ms en esta prueba. Los datos locales no predicen cold starts, red, cuotas ni rendimiento del servicio real.

## 5. ¿Qué ocurrió con una solicitud concreta?

`local-contract-check-0004` es una segunda cancelación: `http_cases.json` registra 409 y el evento JSON correlacionado tiene endpoint `POST /orders/{id}/cancel`, outcome `client_error`, error_type `invalid_state`, categoría books y segmento premium. `local-contract-check-0010` correlaciona un 500 con `simulated_failure`.

En la prueba del simulador, los 60 request IDs del CSV aparecen exactamente una vez en los logs medidos, sin diferencias de código. Los logs de preparación están excluidos por fase y los intentos de comprobación usan otra corrida. El flujo real pendiente es CSV → filtro request_id/run_id en Logs Explorer → `correlate_request.sql` → dashboard.

## Discrepancias y validaciones pendientes

- Las métricas nativas y la consulta SQL de errores ya se comprobaron con el smoke GCP; todavía falta validación del panel SQL de latencia y la comparación cuantitativa de las cuatro fuentes para la hora oficial.
- Las métricas de logs se crearon a las 02:02:58/59Z, antes del primer tráfico de pruebas remoto; la evidencia está guardada en evidence/gcp-setup/.
- El análisis oficial debe usar t0 a fin de drenado, excluyendo tráfico de preparación/smoke. El simulador incorpora 120 s de quietud antes de t0 para separar bins nativos.
- Los contadores de la plataforma pueden incluir solicitudes rechazadas antes del manejador; los logs de aplicación solo cuentan las atendidas. Un timeout cliente puede coexistir con un backend completado e incluso una escritura confirmada.
- Los widgets SQL tienen filtros y tiempos propios; no heredan filtros del dashboard. Sus percentiles son aproximados y los de la métrica de logs dependen de los buckets.
- Faltan exportación del JSON real, captura legible del dashboard y registro de limpieza. Después de preservar esas evidencias, hay que revisar y destruir los recursos propios.
