WITH events AS (
  SELECT TIMESTAMP_TRUNC(timestamp, MINUTE) AS minute,
    COALESCE(JSON_VALUE(json_payload.customer_tier), 'unknown') AS customer_tier,
    COALESCE(JSON_VALUE(json_payload.endpoint), 'unknown') AS endpoint,
    SAFE_CAST(JSON_VALUE(json_payload.latency_ms) AS FLOAT64) AS latency_ms
  FROM `demo-observable-lab.global._Default._Default`
  WHERE timestamp >= TIMESTAMP('2026-10-31T01:05:09.492136+00:00') AND timestamp < TIMESTAMP('2026-10-31T01:05:16.693745+00:00')
    AND resource.type = 'cloud_run_revision'
    AND JSON_VALUE(resource.labels.service_name) = 'orders-api'
    AND JSON_VALUE(json_payload.message) = 'request_completed'
    AND JSON_VALUE(json_payload.run_id) = 'local-smoke'
    AND JSON_VALUE(json_payload.phase) = 'traffic'
)
SELECT minute, customer_tier, endpoint, COUNT(*) AS requests,
  APPROX_QUANTILES(latency_ms, 100)[OFFSET(50)] AS p50_ms,
  APPROX_QUANTILES(latency_ms, 100)[OFFSET(95)] AS p95_ms
FROM events
WHERE latency_ms IS NOT NULL
GROUP BY minute, customer_tier, endpoint
ORDER BY minute, customer_tier, endpoint
