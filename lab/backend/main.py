"""HTTP Cloud Run function; exactamente un evento JSON de cierre por invocación."""

import json
import math
import os
import random
import re
import time
from dataclasses import dataclass
from uuid import uuid4

import functions_framework
from flask import Response

if __package__:
    from .repository import InvalidState, NotFound, get_repository
else:  # El ZIP de Cloud Functions sitúa main.py en la raíz.
    from repository import InvalidState, NotFound, get_repository

CATEGORIES = ("electronics", "books", "clothing")
TIERS = ("standard", "premium")
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")


@dataclass(frozen=True)
class Settings:
    failure_rate: float
    extra_latency_ms: float

    @classmethod
    def from_env(cls):
        rate = float(os.getenv("FAILURE_RATE", "0.02"))
        latency = float(os.getenv("EXTRA_LATENCY_MS", "0"))
        if not math.isfinite(rate) or not 0 <= rate <= 1:
            raise ValueError("FAILURE_RATE debe estar entre 0 y 1")
        if not math.isfinite(latency) or latency < 0:
            raise ValueError("EXTRA_LATENCY_MS debe ser finita y no negativa")
        return cls(rate, latency)


SETTINGS = Settings.from_env()  # Configuración inválida impide arrancar la revisión.


class ApiError(Exception):
    def __init__(self, status, kind, message):
        self.status, self.kind, self.message = status, kind, message


def valid_amount(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value > 0
    except OverflowError:
        return False


def validate_payload(payload):
    if not isinstance(payload, dict):
        raise ApiError(400, "invalid_payload", "Se requiere un objeto JSON")
    if (
        payload.get("category") not in CATEGORIES
        or payload.get("customer_tier") not in TIERS
        or not valid_amount(payload.get("amount"))
    ):
        raise ApiError(400, "invalid_payload", "category, customer_tier o amount inválidos")
    # Firestore tiene enteros de 64 bits; guardar amount como double admite números
    # finitos grandes que cumplen el contrato HTTP sin desbordar su tipo entero.
    return {
        "category": payload["category"],
        "customer_tier": payload["customer_tier"],
        "amount": float(payload["amount"]),
    }


@functions_framework.http
def handle(request):
    started = time.monotonic()
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    run_id = request.headers.get("X-Lab-Run-ID") or "unscoped"
    attributes = {
        "category": request.headers.get("X-Lab-Category", "unknown"),
        "customer_tier": request.headers.get("X-Lab-Customer-Tier", "unknown"),
        "amount": None,
    }
    if attributes["category"] not in CATEGORIES:
        attributes["category"] = "unknown"
    if attributes["customer_tier"] not in TIERS:
        attributes["customer_tier"] = "unknown"
    endpoint, status, error_type = f"{request.method} /unknown", 500, "internal_error"
    body = {"error": {"type": error_type, "message": "Error interno"}}
    headers = {"X-Request-ID": request_id}
    try:
        time.sleep(SETTINGS.extra_latency_ms / 1000)
        if not RUN_ID.fullmatch(run_id):
            raise ApiError(400, "invalid_payload", "X-Lab-Run-ID inválido")
        path = request.path
        resource = re.fullmatch(r"/orders/([A-Za-z0-9_-]{1,128})(/cancel)?", path)
        if path == "/orders":
            endpoint = f"{request.method} /orders"
            allowed = "POST"
        elif resource:
            endpoint = f"{request.method} /orders/{{id}}" + ("/cancel" if resource[2] else "")
            allowed = "POST" if resource[2] else "GET"
        else:
            raise ApiError(404, "not_found", "Ruta inexistente")
        if request.method != allowed:
            headers["Allow"] = allowed
            raise ApiError(405, "method_not_allowed", "Método no permitido")

        if path == "/orders":
            payload = request.get_json(silent=True)
            if isinstance(payload, dict):
                # Nunca emitir NaN/Infinity ni valores de cardinalidad sin acotar.
                for key, vocabulary in (("category", CATEGORIES), ("customer_tier", TIERS)):
                    if payload.get(key) in vocabulary:
                        attributes[key] = payload[key]
                if valid_amount(payload.get("amount")):
                    attributes["amount"] = payload["amount"]
            attributes.update(validate_payload(payload))
        else:
            order = get_repository().get(run_id, resource[1])
            attributes.update({key: order[key] for key in attributes})
            if resource[2] and order["status"] != "created":
                raise InvalidState(order)

        if random.random() < SETTINGS.failure_rate:
            raise ApiError(500, "simulated_failure", "Falla simulada")
        if path == "/orders":
            order = get_repository().create(run_id, attributes)
            status = 201
        elif resource[2]:
            order = get_repository().cancel(run_id, resource[1])
            status = 200
        else:
            status = 200
        body, error_type = {"order": order}, None
    except NotFound:
        status, error_type = 404, "not_found"
        body = {"error": {"type": error_type, "message": "Pedido inexistente"}}
    except InvalidState as exc:
        attributes.update({key: exc.order[key] for key in attributes})
        status, error_type = 409, "invalid_state"
        body = {"error": {"type": error_type, "message": "El pedido ya está cancelado"}}
    except ApiError as exc:
        status, error_type = exc.status, exc.kind
        body = {"error": {"type": exc.kind, "message": exc.message}}
    except Exception as exc:
        # Diagnóstico sin traceback adicional ni mensajes potencialmente sensibles.
        status, error_type = 500, "internal_error"
        body = {"error": {"type": error_type, "message": "Error interno"}}
        attributes["exception_class"] = type(exc).__name__
    finally:
        body["request_id"] = request_id
        event = {
            "severity": "INFO" if status < 400 else "WARNING" if status < 500 else "ERROR",
            "message": "request_completed",
            "request_id": request_id,
            "endpoint": endpoint,
            "status_code": status,
            "outcome": "success"
            if status < 400
            else "client_error"
            if status < 500
            else "server_error",
            "error_type": error_type,
            "latency_ms": round((time.monotonic() - started) * 1000, 3),
            **attributes,
            "run_id": run_id,
            "phase": "preparation"
            if request.headers.get("X-Lab-Phase") == "preparation"
            else "traffic",
        }
        print(json.dumps(event, ensure_ascii=False, allow_nan=False), flush=True)
    return Response(
        json.dumps(body, ensure_ascii=False, allow_nan=False),
        status=status,
        headers=headers,
        content_type="application/json",
    )
