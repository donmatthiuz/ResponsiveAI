"""Renderiza SQL y dashboard con los tiempos reales de summary.json, sin llamar APIs."""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render(project, service, summary, request_id="REEMPLAZAR", source=None):
    replacements = {
        "__PROJECT_ID__": project,
        "__SERVICE_NAME__": service,
        "__RUN_ID__": summary["run_id"],
        "__START_UTC__": summary["window_start_utc"],
        "__END_UTC__": summary["finished_at_utc"],
        "__REQUEST_ID__": request_id,
    }
    # Estos valores se insertan como literales SQL; rechazar comillas, no interpolar comandos.
    if any(not re.fullmatch(r"[A-Za-z0-9_.:+-]+", value) for value in replacements.values()):
        raise ValueError("Identificadores/fechas no válidos para las plantillas")
    queries = {}
    for path in (ROOT / "observability/queries").glob("*.sql"):
        sql = path.read_text()
        for key, value in replacements.items():
            sql = sql.replace(key, value)
        queries[path.name] = sql
    template = json.loads((ROOT / "observability/dashboard.json").read_text())
    dashboard = source or template
    # Actualizar solo nuestros dos paneles SQL y conservar otros widgets del JSON exportado.
    dashboard = json.loads(json.dumps(dashboard))
    for widget in dashboard.get("gridLayout", {}).get("widgets", []):
        name = None
        if widget.get("title") == "Errores de cliente / total por categoría · SQL":
            name = "errors_by_category.sql"
        elif widget.get("title") == "Latencia por segmento / operación · SQL":
            name = "latency_by_tier.sql"
        if name:
            if name == "latency_by_tier.sql":
                datasets = widget["xyChart"].get("dataSets", [])
                measures = [
                    measure.get("column")
                    for dataset in datasets
                    for measure in dataset.get("measures", [])
                ]
                breakdowns = [
                    item.get("column")
                    for dataset in datasets
                    for item in dataset.get("breakdowns", [])
                ]
                if len(datasets) != 1 or measures != ["latency_ms"] or breakdowns != ["series"]:
                    # Migrar exportaciones previas con p50/p95 como medidas separadas.
                    current = next(
                        item
                        for item in template["gridLayout"]["widgets"]
                        if item.get("title") == widget["title"]
                    )
                    widget["xyChart"]["dataSets"] = json.loads(
                        json.dumps(current["xyChart"]["dataSets"])
                    )
            for dataset in widget.get("xyChart", {}).get("dataSets", []):
                dataset["timeSeriesQuery"] = {"opsAnalyticsQuery": {"sql": queries[name]}}
    encoded = json.dumps(dashboard)
    encoded = encoded.replace('"__ERROR_SQL__"', json.dumps(queries["errors_by_category.sql"]))
    encoded = encoded.replace('"__LATENCY_SQL__"', json.dumps(queries["latency_by_tier.sql"]))
    for key, value in replacements.items():
        encoded = encoded.replace(key, value)
    return json.loads(encoded), queries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--service", default="orders-api")
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--request-id", default="REEMPLAZAR")
    parser.add_argument("--dashboard-source", type=Path, help="JSON exportado con widgets manuales")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text())
    source = json.loads(args.dashboard_source.read_text()) if args.dashboard_source else None
    dashboard, queries = render(args.project, args.service, summary, args.request_id, source)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, sql in queries.items():
        (args.output_dir / name).write_text(sql)
    # Quitar campos de solo lectura; la identidad se pasa al comando gcloud update.
    for key in ("name", "etag"):
        dashboard.pop(key, None)
    (args.output_dir / "dashboard.json").write_text(json.dumps(dashboard, indent=2) + "\n")
    print(args.output_dir / "dashboard.json")


if __name__ == "__main__":
    main()
