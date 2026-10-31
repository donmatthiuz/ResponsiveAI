-- Plantilla: renderizar parámetros con scripts/render_observability.py.
WITH events AS (
  SELECT timestamp,
    SAFE_CAST(JSON_VALUE(json_payload.status_code) AS INT64) AS status_code
  FROM `demo-observable-lab.global._Default._Default`
  WHERE timestamp >= TIMESTAMP('2026-10-31T01:05:09.492136+00:00') AND timestamp < TIMESTAMP('2026-10-31T01:05:16.693745+00:00')
    AND resource.type = 'cloud_run_revision'
    AND JSON_VALUE(resource.labels.service_name) = 'orders-api'
    AND JSON_VALUE(json_payload.message) = 'request_completed'
    AND JSON_VALUE(json_payload.run_id) = 'local-smoke'
    AND JSON_VALUE(json_payload.phase) = 'traffic'
)
SELECT TIMESTAMP_TRUNC(timestamp, MINUTE) AS minute,
  CASE WHEN status_code BETWEEN 200 AND 299 THEN '2xx'
       WHEN status_code BETWEEN 400 AND 499 THEN '4xx'
       WHEN status_code BETWEEN 500 AND 599 THEN '5xx' ELSE 'other' END AS http_class,
  COUNT(*) AS requests
FROM events
GROUP BY minute, http_class
ORDER BY minute, http_class
