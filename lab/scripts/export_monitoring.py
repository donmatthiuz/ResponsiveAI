"""Exporta series reales de Monitoring y el dashboard final; solo lectura en GCP."""

import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

METRICS = {
    "native_count": "run.googleapis.com/request_count",
    "native_latency": "run.googleapis.com/request_latencies",
    "log_count": "logging.googleapis.com/user/lab_request_completed_count",
    "log_latency": "logging.googleapis.com/user/lab_request_latency_ms",
}


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def export(project, service, region, directory, dashboard_name):
    summary = json.loads((directory / "summary.json").read_text())
    start = datetime.fromisoformat(summary["window_start_utc"])
    finish = datetime.fromisoformat(summary["finished_at_utc"])
    metric_start = start.replace(second=0, microsecond=0)
    metric_end = finish.replace(second=0, microsecond=0) + timedelta(minutes=1)
    # Incluir el intervalo previo permite identificar el pico de preparación.
    comparison_start = metric_start - timedelta(minutes=3)
    output = directory / "monitoring"
    output.mkdir(exist_ok=True)
    token = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        check=True,
        capture_output=True,
        text=True,
        timeout=45,
    ).stdout.strip()

    def get(url):
        request = Request(url, headers={"Authorization": "Bearer " + token})
        with urlopen(request, timeout=90) as response:
            return json.load(response)

    def write(name, data):
        (output / name).write_text(json.dumps(data, indent=2) + "\n")

    def metric_filter(metric):
        return (
            f'metric.type={json.dumps(metric)} AND resource.type="cloud_run_revision" '
            f"AND resource.labels.project_id={json.dumps(project)} "
            f"AND resource.labels.service_name={json.dumps(service)} "
            f"AND resource.labels.location={json.dumps(region)}"
        )

    base = f"https://monitoring.googleapis.com/v3/projects/{quote(project, safe='')}"

    def series(metric, aggregation=None):
        params = {
            "filter": metric_filter(metric),
            "interval.startTime": stamp(comparison_start),
            "interval.endTime": stamp(metric_end),
            "view": "FULL",
            "pageSize": 100000,
        }
        if aggregation:
            params.update(aggregation)
        rows, pages = [], 0
        while True:
            data = get(base + "/timeSeries?" + urlencode(params))
            rows.extend(data.get("timeSeries", []))
            pages += 1
            if not data.get("nextPageToken"):
                break
            params["pageToken"] = data["nextPageToken"]
        return {"metric": metric, "pages": pages, "timeSeries": rows}

    def one_metric(item):
        key, metric = item
        descriptor = get(base + "/metricDescriptors/" + quote(metric, safe="/"))
        write(key + "_descriptor.json", descriptor)
        data = series(metric)
        write(key + ".json", data)
        return {"name": key, "series": len(data["timeSeries"]), "unit": descriptor.get("unit")}

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(one_metric, METRICS.items()))
    for percentile in (50, 95):
        data = series(
            METRICS["native_latency"],
            {
                "aggregation.alignmentPeriod": "60s",
                "aggregation.perSeriesAligner": "ALIGN_SUM",
                "aggregation.crossSeriesReducer": f"REDUCE_PERCENTILE_{percentile}",
            },
        )
        write(f"native_p{percentile}.json", data)
    dashboard = get("https://monitoring.googleapis.com/v1/" + quote(dashboard_name, safe="/"))
    (directory / "dashboard.json").write_text(json.dumps(dashboard, indent=2) + "\n")
    metadata = {
        "exported_at_utc": stamp(datetime.now(UTC)),
        "project": project,
        "service": service,
        "region": region,
        "run_id": summary["run_id"],
        "measured_start_utc": stamp(start),
        "measured_finish_utc": stamp(finish),
        "metric_start_utc": stamp(metric_start),
        "metric_end_utc": stamp(metric_end),
        "comparison_start_utc": stamp(comparison_start),
        "metrics": results,
        "note": "Contadores sin run_id: contrastar con logs y ventana. Inicio/fin redondeados para incluir bins completos de un minuto; el intervalo previo solo identifica preparación.",
    }
    write("metadata.json", metadata)
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--service", default="orders-api")
    parser.add_argument("--region", default="us-central1")
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--dashboard-name", required=True)
    args = parser.parse_args()
    export(args.project, args.service, args.region, args.evidence_dir, args.dashboard_name)
