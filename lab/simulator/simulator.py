"""Plan reproducible y despacho HTTP concurrente; no reintenta tráfico medido."""

import argparse
import asyncio
import csv
import hashlib
import json
import math
import re
import subprocess
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import numpy as np

CATEGORIES = ("electronics", "books", "clothing")
TIERS = ("standard", "premium")
OPERATIONS = ("create", "get", "cancel")
FIELDS = [
    "run_id",
    "request_id",
    "scheduled_at_utc",
    "scheduled_offset_s",
    "sent_at_utc",
    "dispatch_delay_ms",
    "operation",
    "intended_event",
    "expected_status_code",
    "status_code",
    "client_latency_ms",
    "transport_error",
    "category",
    "customer_tier",
    "scenario",
]


def utcnow():
    return datetime.now(UTC)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_config(config):
    try:
        url = urlsplit(config["target_url"])
        if (
            url.scheme not in ("http", "https")
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or "<" in url.netloc
        ):
            raise ValueError("target_url debe ser una URL HTTP(S) real sin credenciales/query")
        _ = url.port
        if type(config["n_requests"]) is not int or config["n_requests"] <= 0:
            raise ValueError("n_requests debe ser un entero positivo")
        if type(config["seed"]) is not int or config["seed"] < 0:
            raise ValueError("seed debe ser un entero no negativo")
        for name in ("mu_min", "sigma_min", "invalid_share"):
            if not number(config[name]):
                raise ValueError(f"{name} debe ser finito")
        if not 0 <= config["mu_min"] <= 60 or config["sigma_min"] <= 0:
            raise ValueError("mu_min debe estar en [0,60] y sigma_min > 0")
        if not 0 <= config["invalid_share"] <= 1:
            raise ValueError("invalid_share debe estar en [0,1]")
        scenarios = config.get("scenarios", [])
        if not isinstance(scenarios, list):
            raise ValueError("scenarios debe ser una lista")
        for i, scenario in enumerate(scenarios):
            if scenario["effect"] != "double_errors" or scenario["category"] not in CATEGORIES:
                raise ValueError("Escenario/efecto/categoría desconocido")
            start, end = scenario["start_min"], scenario["end_min"]
            if not number(start) or not number(end) or not 0 <= start < end <= 60:
                raise ValueError("Escenario requiere 0 <= start_min < end_min <= 60")
            for previous in scenarios[:i]:
                if (
                    previous["category"] == scenario["category"]
                    and start < previous["end_min"]
                    and previous["start_min"] < end
                ):
                    raise ValueError("Escenarios superpuestos para una categoría")
    except (KeyError, TypeError, OverflowError) as exc:
        raise ValueError(f"Configuración incompleta o inválida: {exc}") from exc
    return config


def effective_invalid_share(config, minute, category):
    for scenario in config.get("scenarios", []):
        if (
            scenario["category"] == category
            and scenario["start_min"] <= minute < scenario["end_min"]
        ):
            return min(1.0, 2 * config["invalid_share"]), "double_errors"
    return config["invalid_share"], "baseline"


@dataclass(frozen=True)
class Event:
    request_id: str
    scheduled_offset_s: float
    operation: str
    intended_event: str
    expected_status_code: int
    category: str
    customer_tier: str
    amount: float
    scenario: str
    resource_key: str


def build_plan(config, run_id):
    validate_config(config)
    rng = np.random.default_rng(config["seed"])
    n = config["n_requests"]
    chunks, remaining = [], n
    while remaining:
        values = rng.normal(config["mu_min"], config["sigma_min"], max(remaining, 32))
        accepted = values[(values >= 0) & (values <= 60)][:remaining]
        chunks.append(accepted)
        remaining -= len(accepted)
    minutes = np.sort(np.concatenate(chunks))
    result = []
    for index, minute in enumerate(minutes):
        category = str(rng.choice(CATEGORIES))
        tier = str(rng.choice(TIERS))
        operation = str(rng.choice(OPERATIONS, p=[0.5, 0.3, 0.2]))
        probability, scenario = effective_invalid_share(config, minute, category)
        intention = "valid"
        if rng.random() < probability:
            intention = str(rng.choice(("invalid_payload", "not_found", "invalid_state")))
            operation = {"invalid_payload": "create", "invalid_state": "cancel"}.get(
                intention, str(rng.choice(("get", "cancel")))
            )
        status = {"invalid_payload": 400, "not_found": 404, "invalid_state": 409}.get(
            intention, 201 if operation == "create" else 200
        )
        resource_key = ""
        if intention == "invalid_state":
            resource_key = f"cancelled:{category}:{tier}"
        elif intention == "valid" and operation == "cancel":
            resource_key = f"cancel:{index}:{category}:{tier}"
        elif intention == "valid" and operation == "get":
            resource_key = f"active:{category}:{tier}"
        result.append(
            Event(
                f"{run_id}-request-{index:06d}",
                float(minute * 60),
                operation,
                intention,
                status,
                category,
                tier,
                round(float(rng.uniform(1, 500)), 2),
                scenario,
                resource_key,
            )
        )
    return result


class TokenProvider:
    """Renueva tokens gcloud sin guardarlos en archivos de evidencia."""

    def __init__(self, mode="public", audience="", service_account=None):
        self.mode, self.audience, self.service_account = mode, audience, service_account
        self.token, self.refreshed = "", 0.0
        self.lock = asyncio.Lock()

    async def headers(self):
        if self.mode == "public":
            return {}
        async with self.lock:
            if not self.token or time.monotonic() - self.refreshed >= 2400:
                command = ["gcloud", "auth", "print-identity-token"]
                if self.service_account:
                    command += [
                        f"--impersonate-service-account={self.service_account}",
                        f"--audiences={self.audience}",
                    ]
                result = await asyncio.to_thread(
                    subprocess.run, command, check=True, capture_output=True, text=True, timeout=45
                )
                self.token, self.refreshed = result.stdout.strip(), time.monotonic()
                if not self.token:
                    raise RuntimeError("gcloud no devolvió un token de identidad")
        return {"Authorization": f"Bearer {self.token}"}


def lab_headers(run_id, request_id, category, tier, phase="traffic"):
    return {
        "X-Request-ID": request_id,
        "X-Lab-Run-ID": run_id,
        "X-Lab-Category": category,
        "X-Lab-Customer-Tier": tier,
        "X-Lab-Phase": phase,
    }


async def prepare(client, config, plan, run_id, output_dir, auth):
    required = {event.resource_key: event for event in plan if event.resource_key}
    prepared = {}
    semaphore = asyncio.Semaphore(10)
    with (output_dir / "preparation.jsonl").open("x", encoding="utf-8", buffering=1) as log:

        async def resource(key, event):
            async with semaphore:
                for attempt in range(1, 4):
                    prefix = hashlib.sha256(key.encode()).hexdigest()[:16]
                    headers = lab_headers(
                        run_id,
                        f"{run_id}-prep-{prefix}-{attempt}",
                        event.category,
                        event.customer_tier,
                        "preparation",
                    )
                    headers.update(await auth.headers())
                    try:
                        response = await client.post(
                            config["target_url"].rstrip("/") + "/orders",
                            headers=headers,
                            json={
                                "category": event.category,
                                "customer_tier": event.customer_tier,
                                "amount": event.amount,
                            },
                        )
                        log.write(
                            json.dumps(
                                {
                                    "request_id": headers["X-Request-ID"],
                                    "resource_key": key,
                                    "attempt": attempt,
                                    "step": "create",
                                    "status_code": response.status_code,
                                    "at_utc": utcnow().isoformat(),
                                }
                            )
                            + "\n"
                        )
                        if response.status_code != 201:
                            if response.status_code < 500:
                                raise RuntimeError(
                                    f"Preparación rechazada: HTTP {response.status_code}"
                                )
                            raise httpx.RequestError(f"HTTP {response.status_code}")
                        order_id = response.json()["order"]["id"]
                        if key.startswith("cancelled:"):
                            headers["X-Request-ID"] += "-cancel"
                            response = await client.post(
                                config["target_url"].rstrip("/") + f"/orders/{order_id}/cancel",
                                headers=headers,
                            )
                            log.write(
                                json.dumps(
                                    {
                                        "request_id": headers["X-Request-ID"],
                                        "resource_key": key,
                                        "attempt": attempt,
                                        "step": "cancel",
                                        "status_code": response.status_code,
                                        "at_utc": utcnow().isoformat(),
                                    }
                                )
                                + "\n"
                            )
                            if response.status_code != 200:
                                if response.status_code < 500:
                                    raise RuntimeError(
                                        f"Cancelación preparatoria: HTTP {response.status_code}"
                                    )
                                raise httpx.RequestError(f"HTTP {response.status_code}")
                        prepared[key] = order_id
                        return
                    except httpx.RequestError as exc:
                        log.write(
                            json.dumps(
                                {
                                    "resource_key": key,
                                    "attempt": attempt,
                                    "error": str(exc),
                                    "at_utc": utcnow().isoformat(),
                                }
                            )
                            + "\n"
                        )
                        if attempt == 3:
                            raise RuntimeError(
                                f"Preparación incompleta tras 3 intentos: {key}"
                            ) from exc
                        await asyncio.sleep(0.2 * attempt)

        # TaskGroup cancela el resto si falta cualquier recurso; nunca inicia el reloj incompleto.
        async with asyncio.TaskGroup() as group:
            for key, event in required.items():
                group.create_task(resource(key, event))
    return prepared


def request_spec(event, prepared):
    if event.operation == "create":
        payload = {
            "category": event.category,
            "customer_tier": event.customer_tier,
            "amount": -1 if event.intended_event == "invalid_payload" else event.amount,
        }
        return "POST", "/orders", payload
    order_id = prepared.get(event.resource_key)
    if event.intended_event == "not_found":
        order_id = "missing-" + hashlib.sha256(event.request_id.encode()).hexdigest()[:32]
    if not order_id:
        raise RuntimeError(f"Falta recurso preparado para {event.request_id}")
    return (
        ("GET", f"/orders/{order_id}", None)
        if event.operation == "get"
        else ("POST", f"/orders/{order_id}/cancel", None)
    )


def save_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    temporary.replace(path)


def save_schedule(path, plan, run_id, t0=None, scale=1):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["run_id", "scheduled_at_utc", *Event.__dataclass_fields__]
        )
        writer.writeheader()
        for event in plan:
            writer.writerow(
                {
                    "run_id": run_id,
                    "scheduled_at_utc": (
                        t0 + timedelta(seconds=event.scheduled_offset_s * scale)
                    ).isoformat()
                    if t0
                    else "",
                    **asdict(event),
                }
            )


def percentiles(values):
    return {str(p): float(np.percentile(values, p)) for p in (50, 95, 99)} if values else {}


async def dispatch(client, config, plan, prepared, run_id, output, scale, auth):
    rows, tasks = [], []
    # Guardar fechas absolutas antes de tomar el reloj monotónico evita retrasar el primer envío.
    t0_utc = utcnow() + timedelta(seconds=0.1)
    save_schedule(output.parent / "schedule.csv", plan, run_id, t0_utc, scale)
    t0 = time.monotonic() + (t0_utc - utcnow()).total_seconds()
    interrupted = True
    incomplete_reason = "interrupted"
    with output.open("x", newline="", encoding="utf-8", buffering=1) as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()

        async def send(event):
            row = {
                "run_id": run_id,
                "request_id": event.request_id,
                "scheduled_at_utc": (
                    t0_utc + timedelta(seconds=event.scheduled_offset_s * scale)
                ).isoformat(),
                "scheduled_offset_s": event.scheduled_offset_s,
                "operation": event.operation,
                "intended_event": event.intended_event,
                "expected_status_code": event.expected_status_code,
                "category": event.category,
                "customer_tier": event.customer_tier,
                "scenario": event.scenario,
                "status_code": "",
                "transport_error": "",
            }
            start = time.monotonic()
            row["sent_at_utc"] = utcnow().isoformat()
            row["dispatch_delay_ms"] = max(
                0, (start - t0 - event.scheduled_offset_s * scale) * 1000
            )
            try:
                method, path, payload = request_spec(event, prepared)
                headers = lab_headers(run_id, event.request_id, event.category, event.customer_tier)
                headers.update(await auth.headers())
                response = await client.request(
                    method, config["target_url"].rstrip("/") + path, json=payload, headers=headers
                )
                row["status_code"] = response.status_code
            except asyncio.CancelledError:
                row["transport_error"] = "cancelled"
                raise
            except Exception as exc:
                row["transport_error"] = f"{type(exc).__name__}: {exc}"
            finally:
                row["client_latency_ms"] = (time.monotonic() - start) * 1000
                # No await: un único bucle de eventos serializa escritura y flush por fila.
                writer.writerow(row)
                stream.flush()
                rows.append(row)

        try:
            for event in plan:
                await asyncio.sleep(
                    max(0, t0 + event.scheduled_offset_s * scale - time.monotonic())
                )
                if time.monotonic() > t0 + 3600 * scale:
                    incomplete_reason = "send_window_expired"
                    break
                tasks.append(asyncio.create_task(send(event)))
            await asyncio.sleep(max(0, t0 + 3600 * scale - time.monotonic()))
            await asyncio.gather(*tasks)
            interrupted = len(tasks) != len(plan)
        finally:
            if interrupted:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            finished = utcnow()
            summary = {
                "run_id": run_id,
                "config": config,
                "seed": config["seed"],
                "time_scale": scale,
                "execution_kind": "accelerated_test" if scale != 1 else "one_hour_execution",
                "status": "incomplete" if interrupted else "complete",
                "incomplete_reason": incomplete_reason if interrupted else None,
                "window_start_utc": t0_utc.isoformat(),
                "window_end_utc": (t0_utc + timedelta(seconds=3600 * scale)).isoformat(),
                "finished_at_utc": finished.isoformat(),
                "elapsed_s": time.monotonic() - t0,
                "programmed": len(plan),
                "sent": len(rows),
                "completed": len(rows),
                "http_responses": sum(bool(row["status_code"]) for row in rows),
                "http_status_codes": dict(
                    Counter(str(row["status_code"]) for row in rows if row["status_code"])
                ),
                "transport_errors": dict(
                    Counter(row["transport_error"] for row in rows if row["transport_error"])
                ),
                "intentions": dict(Counter(row["intended_event"] for row in rows)),
                "operations": dict(Counter(row["operation"] for row in rows)),
                "client_latency_ms_percentiles": percentiles(
                    [row["client_latency_ms"] for row in rows]
                ),
                "dispatch_delay_ms_percentiles": percentiles(
                    [row["dispatch_delay_ms"] for row in rows]
                ),
            }
            save_json(output.parent / "summary.json", summary)
    return summary


async def run(config, output, run_id, dry_run=False, time_scale=1.0, auth=None, transport=None):
    validate_config(config)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", run_id):
        raise ValueError("run_id inválido; máximo 128 caracteres alfanuméricos/_.-")
    if not number(time_scale) or time_scale <= 0:
        raise ValueError("time_scale debe ser finito y positivo")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    for path in (output, output.parent / "schedule.csv", output.parent / "summary.json"):
        if path.exists():
            raise ValueError(f"No se sobrescribe evidencia existente: {path}")
    plan = build_plan(config, run_id)
    save_json(output.parent / "config.json", {**config, "run_id": run_id, "time_scale": time_scale})
    save_schedule(output.parent / "schedule.csv", plan, run_id, scale=time_scale)
    if dry_run:
        summary = {
            "status": "dry_run",
            "sent": 0,
            "programmed": len(plan),
            "run_id": run_id,
            "time_scale": time_scale,
            "config": config,
        }
        save_json(output.parent / "summary.json", summary)
        return summary
    auth = auth or TokenProvider()
    try:
        await auth.headers()  # Fallar antes de preparar si no hay autenticación disponible.
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(70, connect=10, pool=10),
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=50),
            transport=transport,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            prepared = await prepare(client, config, plan, run_id, output.parent, auth)
            save_json(output.parent / "prepared_resources.json", prepared)
            cooldown = 120 if time_scale == 1 else 0
            save_json(
                output.parent / "preparation_summary.json",
                {
                    "run_id": run_id,
                    "status": "complete",
                    "resources": len(prepared),
                    "finished_at_utc": utcnow().isoformat(),
                    "cooldown_s": cooldown,
                },
            )
            # Separa preparación de la primera agregación nativa de un minuto.
            if cooldown:
                print("Preparación completa. Esperando 120 s sin tráfico antes de t0.", flush=True)
                await asyncio.sleep(cooldown)
            await auth.headers()
            return await dispatch(client, config, plan, prepared, run_id, output, time_scale, auth)
    except BaseException as exc:
        if not (output.parent / "summary.json").exists():
            save_json(
                output.parent / "summary.json",
                {
                    "status": "preparation_failed",
                    "run_id": run_id,
                    "programmed": len(plan),
                    "sent": 0,
                    "error_class": type(exc).__name__,
                    "diagnostic": str(exc),
                    "config": config,
                },
            )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("simulator/requests.csv"))
    parser.add_argument(
        "--run-id", default="run-" + utcnow().strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:8]
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--time-scale", type=float, default=1)
    parser.add_argument("--auth", choices=("public", "gcloud"), default="public")
    parser.add_argument("--impersonate-service-account")
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text())
        summary = asyncio.run(
            run(
                config,
                args.output,
                args.run_id,
                args.dry_run,
                args.time_scale,
                TokenProvider(args.auth, config["target_url"], args.impersonate_service_account),
            )
        )
        print(json.dumps(summary, indent=2))
    except KeyboardInterrupt:
        print("Interrumpido: CSV parcial y summary.json conservados.")
        raise SystemExit(130)
    except Exception as exc:
        parser.exit(1, f"{type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    main()
