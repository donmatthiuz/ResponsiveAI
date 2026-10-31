SELECT timestamp, JSON_VALUE(json_payload.request_id) AS request_id,
  JSON_VALUE(json_payload.endpoint) AS endpoint,
  SAFE_CAST(JSON_VALUE(json_payload.status_code) AS INT64) AS status_code,
  JSON_VALUE(json_payload.error_type) AS error_type,
  SAFE_CAST(JSON_VALUE(json_payload.latency_ms) AS FLOAT64) AS latency_ms,
  json_payload
FROM `adfasdfasfd-1899a.global._Default._Default`
WHERE timestamp >= TIMESTAMP('2026-10-31T02:07:27.947662+00:00') AND timestamp < TIMESTAMP('2026-10-31T02:07:35.148179+00:00')
  AND resource.type = 'cloud_run_revision'
  AND JSON_VALUE(resource.labels.service_name) = 'orders-api'
  AND JSON_VALUE(json_payload.message) = 'request_completed'
  AND JSON_VALUE(json_payload.run_id) = 'smoke-20261031T020723Z'
  AND JSON_VALUE(json_payload.phase) = 'traffic'
  AND JSON_VALUE(json_payload.request_id) = 'REEMPLAZAR'
ORDER BY timestamp
