WITH events AS (
  SELECT timestamp,
    COALESCE(JSON_VALUE(json_payload.category), 'unknown') AS category,
    SAFE_CAST(JSON_VALUE(json_payload.status_code) AS INT64) AS status_code
  FROM `adfasdfasfd-1899a.global._Default._Default`
  WHERE timestamp >= TIMESTAMP('2026-10-31T02:07:27.947662+00:00') AND timestamp < TIMESTAMP('2026-10-31T02:07:35.148179+00:00')
    AND resource.type = 'cloud_run_revision'
    AND JSON_VALUE(resource.labels.service_name) = 'orders-api'
    AND JSON_VALUE(json_payload.message) = 'request_completed'
    AND JSON_VALUE(json_payload.run_id) = 'smoke-20261031T020723Z'
    AND JSON_VALUE(json_payload.phase) = 'traffic'
)
SELECT TIMESTAMP_TRUNC(timestamp, MINUTE) AS minute, category,
  COUNT(*) AS requests,
  COUNTIF(status_code BETWEEN 400 AND 499) AS client_errors,
  COUNTIF(status_code BETWEEN 500 AND 599) AS server_errors,
  SAFE_DIVIDE(COUNTIF(status_code BETWEEN 400 AND 499), COUNT(*)) AS client_error_rate,
  SAFE_DIVIDE(COUNTIF(status_code BETWEEN 500 AND 599), COUNT(*)) AS server_error_rate
FROM events
GROUP BY minute, category
ORDER BY minute, category
