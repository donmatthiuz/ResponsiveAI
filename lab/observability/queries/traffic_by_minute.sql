-- Plantilla: renderizar parámetros con scripts/render_observability.py.
WITH events AS (
  SELECT timestamp,
    SAFE_CAST(JSON_VALUE(json_payload.status_code) AS INT64) AS status_code
  FROM `__PROJECT_ID__.global._Default._Default`
  WHERE timestamp >= TIMESTAMP('__START_UTC__') AND timestamp < TIMESTAMP('__END_UTC__')
    AND resource.type = 'cloud_run_revision'
    AND JSON_VALUE(resource.labels.service_name) = '__SERVICE_NAME__'
    AND JSON_VALUE(json_payload.message) = 'request_completed'
    AND JSON_VALUE(json_payload.run_id) = '__RUN_ID__'
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
