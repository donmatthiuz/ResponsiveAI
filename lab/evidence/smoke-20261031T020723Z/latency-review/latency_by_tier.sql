WITH events AS (
  SELECT TIMESTAMP_TRUNC(timestamp, MINUTE) AS minute,
    COALESCE(JSON_VALUE(json_payload.customer_tier), 'unknown') AS customer_tier,
    COALESCE(JSON_VALUE(json_payload.endpoint), 'unknown') AS endpoint,
    SAFE_CAST(JSON_VALUE(json_payload.latency_ms) AS FLOAT64) AS latency_ms
  FROM `adfasdfasfd-1899a.global._Default._Default`
  WHERE timestamp >= TIMESTAMP('2026-10-31T02:07:27.947662+00:00') AND timestamp < TIMESTAMP('2026-10-31T02:07:35.148179+00:00')
    AND resource.type = 'cloud_run_revision'
    AND JSON_VALUE(resource.labels.service_name) = 'orders-api'
    AND JSON_VALUE(json_payload.message) = 'request_completed'
    AND JSON_VALUE(json_payload.run_id) = 'smoke-20261031T020723Z'
    AND JSON_VALUE(json_payload.phase) = 'traffic'
), aggregated AS (
  SELECT minute, customer_tier, endpoint, COUNT(*) AS requests,
    APPROX_QUANTILES(latency_ms, 100)[OFFSET(50)] AS p50_ms,
    APPROX_QUANTILES(latency_ms, 100)[OFFSET(95)] AS p95_ms
  FROM events
  WHERE latency_ms IS NOT NULL
  GROUP BY minute, customer_tier, endpoint
)
-- Una medida numérica y una etiqueta de serie permiten desglosar ambos percentiles.
-- requests es el tamaño del grupo y se repite por percentil; no sumar ambas filas.
SELECT minute, customer_tier, endpoint, requests,
  'p50' AS percentile, p50_ms AS latency_ms,
  CONCAT(customer_tier, ' / ', endpoint, ' / p50') AS series
FROM aggregated
UNION ALL
SELECT minute, customer_tier, endpoint, requests,
  'p95' AS percentile, p95_ms AS latency_ms,
  CONCAT(customer_tier, ' / ', endpoint, ' / p95') AS series
FROM aggregated
ORDER BY minute, customer_tier, endpoint, percentile
