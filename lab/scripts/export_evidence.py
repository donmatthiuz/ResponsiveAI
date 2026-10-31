"""Exporta dashboard REST y logs reales sin almacenar tokens ni credenciales."""

import argparse
import json
import subprocess
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


def command_json(command):
    result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=120)
    return json.loads(result.stdout)


def export(project, directory, dashboard_name):
    summary = json.loads((directory / "summary.json").read_text())
    start, end = summary["window_start_utc"], summary["finished_at_utc"]
    run_id = summary["run_id"]
    filters = (
        f'resource.type="cloud_run_revision" AND jsonPayload.message="request_completed" '
        f'AND jsonPayload.run_id={json.dumps(run_id)} AND jsonPayload.phase="traffic" '
        f"AND timestamp>={json.dumps(start)} AND timestamp<={json.dumps(end)}"
    )
    logs = command_json(
        [
            "gcloud",
            "logging",
            "read",
            filters,
            f"--project={project}",
            "--limit=20000",
            "--order=asc",
            "--format=json",
        ]
    )
    (directory / "logs_sample.jsonl").write_text("".join(json.dumps(log) + "\n" for log in logs))
    token = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()
    url = "https://monitoring.googleapis.com/v1/" + quote(dashboard_name, safe="/")
    request = Request(url, headers={"Authorization": "Bearer " + token})
    with urlopen(request, timeout=60) as response:
        dashboard = json.load(response)
    (directory / "dashboard.json").write_text(json.dumps(dashboard, indent=2) + "\n")
    for metric in ("lab_request_completed_count", "lab_request_latency_ms"):
        data = command_json(
            [
                "gcloud",
                "logging",
                "metrics",
                "describe",
                metric,
                f"--project={project}",
                "--format=json",
            ]
        )
        (directory / f"{metric}.json").write_text(json.dumps(data, indent=2) + "\n")
    print(f"Exportados {len(logs)} logs y dashboard real. Falta capturar dashboard.png en consola.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--dashboard-name", required=True)
    args = parser.parse_args()
    export(args.project, args.evidence_dir, args.dashboard_name)
