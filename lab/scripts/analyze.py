"""Analiza CSV real y, opcionalmente, logs; genera datos y un informe Markdown."""

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


def quantiles(values):
    return {f"p{p}": round(float(np.percentile(values, p)), 3) for p in (50, 95)} if values else {}


def load_logs(path):
    content = path.read_text().strip()
    if not content:
        return []
    entries = (
        json.loads(content)
        if content.startswith("[")
        else [json.loads(line) for line in content.splitlines()]
    )
    return [entry.get("jsonPayload", entry) for entry in entries]


def analyze(directory, logs_path=None):
    summary = json.loads((directory / "summary.json").read_text())
    rows = list(csv.DictReader((directory / "requests.csv").open()))
    run_id = summary["run_id"]
    if any(row["run_id"] != run_id for row in rows):
        raise ValueError("CSV mezcla corridas")
    if len({row["request_id"] for row in rows}) != len(rows):
        raise ValueError("CSV contiene IDs duplicados")
    groups, latency_groups, by_minute = defaultdict(list), defaultdict(list), Counter()
    for row in rows:
        minute = float(row["scheduled_offset_s"]) / 60
        by_minute[int(minute)] += 1
        period = "scenario_window" if 35 <= minute < 45 else "baseline"
        groups[row["category"], period].append(row)
        latency_groups[row["operation"], row["customer_tier"]].append(
            float(row["client_latency_ms"])
        )
    rates = []
    for (category, period), items in sorted(groups.items()):
        statuses = [int(row["status_code"]) for row in items if row["status_code"]]
        invalid = sum(row["intended_event"] != "valid" for row in items)
        client_errors = sum(400 <= status < 500 for status in statuses)
        rates.append(
            {
                "category": category,
                "period": period,
                "attempts": len(items),
                "http_responses": len(statuses),
                "intended_invalid": invalid,
                "intended_invalid_rate": invalid / len(items),
                "client_errors": client_errors,
                "client_error_rate_http": client_errors / len(statuses) if statuses else None,
            }
        )
    classes = Counter(
        "transport_error" if not row["status_code"] else f"{int(row['status_code']) // 100}xx"
        for row in rows
    )
    logs = load_logs(logs_path) if logs_path else []
    measured = [
        event
        for event in logs
        if event.get("run_id") == run_id
        and event.get("phase") == "traffic"
        and event.get("message") == "request_completed"
    ]
    by_id = defaultdict(list)
    for event in measured:
        by_id[event["request_id"]].append(event)
    backend_groups = defaultdict(list)
    for event in measured:
        backend_groups[event["endpoint"], event["customer_tier"]].append(event["latency_ms"])
    paired = sum(row["request_id"] in by_id for row in rows)
    mismatches = [
        row["request_id"]
        for row in rows
        if row["request_id"] in by_id
        and row["status_code"]
        and int(row["status_code"]) != by_id[row["request_id"]][0]["status_code"]
    ]
    data = {
        "run_id": run_id,
        "execution_kind": summary.get("execution_kind"),
        "status": summary["status"],
        "attempts": len(rows),
        "http_classes": dict(classes),
        "http_class_shares_attempts": {key: count / len(rows) for key, count in classes.items()}
        if rows
        else {},
        "intentions": dict(Counter(row["intended_event"] for row in rows)),
        "requests_by_scheduled_minute": dict(sorted(by_minute.items())),
        "category_rates": rates,
        "client_latency_by_operation_tier": {
            " / ".join(key): quantiles(values) for key, values in sorted(latency_groups.items())
        },
        "backend_latency_by_endpoint_tier": {
            " / ".join(key): quantiles(values) for key, values in sorted(backend_groups.items())
        },
        "logs": {
            "provided": bool(logs_path),
            "events_for_run": len(measured),
            "paired_requests": paired,
            "duplicate_ids": sum(len(events) > 1 for events in by_id.values()),
            "status_mismatches": mismatches,
            "error_types": dict(
                Counter(event["error_type"] for event in measured if event.get("error_type"))
            ),
        },
        "dispatch_delay_ms": quantiles([float(row["dispatch_delay_ms"]) for row in rows]),
    }
    (directory / "analysis.json").write_text(json.dumps(data, indent=2) + "\n")
    lines = [
        f"# Análisis de {run_id}",
        "",
        f"Ejecución: **{summary.get('execution_kind', 'desconocida')}**, estado **{summary['status']}**.",
        "",
        "La evidencia local/acelerada no demuestra una hora real ni ingestión en GCP.",
        "",
        f"Ventana de envío: {summary.get('window_start_utc')} a {summary.get('window_end_utc')}; "
        f"fin del drenado: {summary.get('finished_at_utc')}.",
        "",
        f"Intentos: {len(rows)}. Clases HTTP y transporte: `{dict(classes)}`.",
        "",
        "## Volumen",
        "",
        f"Conteos por minuto programado: `{dict(sorted(by_minute.items()))}`.",
        "",
        "Comparar la concentración cerca del minuto 30 con traffic_by_minute.sql y la métrica nativa; "
        "el CSV clasifica por envío programado, el backend registra finalización.",
        "",
        "## Escenario y errores",
        "",
        "Ventana de comparación [35,45) para todas las categorías. Solo electronics tiene double_errors "
        "en la configuración oficial. Tasas HTTP usan respuestas como denominador; intención usa intentos.",
        "",
        "| Categoría | Ventana | n intentos | n respuestas | Inválidas planeadas | 4xx | Tasa 4xx |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in rates:
        rate = item["client_error_rate_http"]
        rate_label = f"{rate:.2%}" if rate is not None else "sin respuestas"
        lines.append(
            f"| {item['category']} | {item['period']} | {item['attempts']} | {item['http_responses']} | "
            f"{item['intended_invalid']} | {item['client_errors']} | {rate_label} |"
        )
    lines += [
        "",
        "No exigir exactamente el doble ni frecuencias exactas en una muestra. "
        "El escenario modifica probabilidad de errores de cliente; FAILURE_RATE se aplica a operaciones válidas.",
        "",
        "## Latencia y correlación",
        "",
        f"Cliente por operación/segmento: `{data['client_latency_by_operation_tier']}`.",
        "",
        f"Backend por endpoint/segmento: `{data['backend_latency_by_endpoint_tier']}`.",
        "",
        f"Retraso de despacho en ms: `{data['dispatch_delay_ms']}`. "
        "La latencia cliente incluye red, pool y autenticación; backend incluye Firestore y demora artificial.",
        "",
        f"Logs: `{data['logs']}`.",
        "",
        "Para investigar una fila, copiar su request_id en correlate_request.sql o filtrar "
        "jsonPayload.request_id en Logs Explorer. Un timeout no demuestra que el backend no haya escrito.",
        "",
        "## Validación de nube pendiente",
        "",
        "Confirmar los descriptores y resultados en el dashboard, esperar ingestión, exportar JSON y captura. "
        "Las métricas incluyen preparación si se amplía la ventana; SQL excluye phase=preparation. "
        "No hay datos de métricas nativas disponibles en este informe de archivos.",
    ]
    (directory / "analysis.md").write_text("\n".join(lines) + "\n")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_dir", type=Path)
    parser.add_argument("--logs", type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.evidence_dir, args.logs), indent=2))
