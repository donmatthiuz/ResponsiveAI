"""Verifica el contrato por HTTP antes de la hora oficial y guarda cada intento."""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

import httpx

from simulator.simulator import TokenProvider, lab_headers, utcnow


async def verify(url, output, run_id, auth, probe_failure=0):
    output.mkdir(parents=True, exist_ok=False)
    cases, index = [], 0
    async with httpx.AsyncClient(timeout=70, trust_env=False) as client:

        async def call(name, method, path, expected, payload=None, raw=None):
            nonlocal index
            for attempt in range(1, 4):
                index += 1
                request_id = f"{run_id}-check-{index:04d}"
                headers = lab_headers(run_id, request_id, "books", "premium")
                headers.update(await auth.headers())
                kwargs = {"json": payload} if raw is None else {"content": raw}
                if raw is not None:
                    headers["Content-Type"] = "application/json"
                response = await client.request(
                    method, url.rstrip("/") + path, headers=headers, **kwargs
                )
                cases.append(
                    {
                        "case": name,
                        "request_id": request_id,
                        "at_utc": utcnow().isoformat(),
                        "expected_status": expected,
                        "status_code": response.status_code,
                        "response_request_id": response.headers.get("X-Request-ID"),
                        "body": response.json(),
                    }
                )
                (output / "http_cases.json").write_text(json.dumps(cases, indent=2) + "\n")
                if response.headers.get("X-Request-ID") != request_id:
                    raise RuntimeError("La API no propagó X-Request-ID")
                if response.status_code == expected:
                    return response
                if response.status_code != 500 or expected >= 400 or attempt == 3:
                    raise RuntimeError(
                        f"{name}: HTTP {response.status_code}; se esperaba {expected}"
                    )
            raise RuntimeError("Caso no confirmado")

        payload = {"category": "books", "customer_tier": "premium", "amount": 12.5}
        created = await call("create", "POST", "/orders", 201, payload)
        order_id = created.json()["order"]["id"]
        await call("get", "GET", f"/orders/{order_id}", 200)
        await call("cancel", "POST", f"/orders/{order_id}/cancel", 200)
        await call("cancel_again", "POST", f"/orders/{order_id}/cancel", 409)
        await call("invalid_amount", "POST", "/orders", 400, {**payload, "amount": True})
        await call("malformed_json", "POST", "/orders", 400, raw="{")
        await call("missing", "GET", "/orders/missing-" + uuid4().hex, 404)
        await call("unknown_route", "GET", "/unknown", 404)
        await call("wrong_method", "DELETE", "/orders", 405)
        # Muestreo acotado: la ausencia de 500 no se confunde con una probabilidad incorrecta.
        for _ in range(probe_failure):
            if any(case["status_code"] == 500 for case in cases):
                break
            await call("probe_simulated_failure", "POST", "/orders", 201, payload)
    result = {
        "run_id": run_id,
        "cases": len(cases),
        "contract_verified": True,
        "observed_500": any(case["status_code"] == 500 for case in cases),
        "note": "Prueba HTTP; todavía requiere correlación con logs y señales en GCP.",
    }
    (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-id", default="check-" + uuid4().hex[:12])
    parser.add_argument("--auth", choices=("public", "gcloud"), default="public")
    parser.add_argument("--impersonate-service-account")
    parser.add_argument("--probe-failure", type=int, default=0)
    args = parser.parse_args()
    asyncio.run(
        verify(
            args.target_url,
            args.output_dir,
            args.run_id,
            TokenProvider(args.auth, args.target_url, args.impersonate_service_account),
            args.probe_failure,
        )
    )


if __name__ == "__main__":
    main()
