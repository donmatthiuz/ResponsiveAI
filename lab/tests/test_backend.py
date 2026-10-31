import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend import main


def events(capsys):
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def test_lifecycle_and_logging(api, payload, capsys):
    call, _ = api
    headers = {"X-Request-ID": "correlation-123", "X-Lab-Run-ID": "test-run"}
    created = call(json=payload, headers=headers)
    assert created.status_code == 201
    order_id = created.json["order"]["id"]
    fetched = call(f"/orders/{order_id}", "GET", headers=headers)
    assert fetched.json["order"]["status"] == "created"
    cancelled = call(f"/orders/{order_id}/cancel", headers=headers)
    assert cancelled.status_code == 200
    repeated = call(f"/orders/{order_id}/cancel", headers=headers)
    assert repeated.status_code == 409
    assert repeated.json["error"]["type"] == "invalid_state"
    missing = call("/orders/missing", "GET", headers=headers)
    assert missing.status_code == 404
    logs = events(capsys)
    assert len(logs) == 5
    assert [item["status_code"] for item in logs] == [201, 200, 200, 409, 404]
    required = {
        "severity",
        "message",
        "request_id",
        "endpoint",
        "status_code",
        "outcome",
        "error_type",
        "latency_ms",
        "category",
        "customer_tier",
        "amount",
        "run_id",
    }
    for response, log in zip([created, fetched, cancelled, repeated, missing], logs, strict=True):
        assert required <= log.keys()
        assert log["request_id"] == response.headers["X-Request-ID"] == "correlation-123"
        assert log["message"] == "request_completed"
        assert log["latency_ms"] >= 0
    assert logs[1]["endpoint"] == "GET /orders/{id}"
    assert logs[3]["category"] == "books"
    assert logs[3]["severity"] == "WARNING"


@pytest.mark.parametrize(
    "amount", [True, False, 0, -1, "2", None, float("nan"), float("inf"), 10**400]
)
def test_invalid_amounts(api, payload, amount, capsys):
    call, repository = api
    response = call(json={**payload, "amount": amount})
    assert response.status_code == 400
    assert not repository.items
    assert events(capsys)[0]["error_type"] == "invalid_payload"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        [],
        None,
        {"category": ["books"]},
        {"category": "other", "customer_tier": "premium", "amount": 1},
        {"category": "books", "customer_tier": "vip", "amount": 1},
    ],
)
def test_invalid_payload(api, payload, capsys):
    response = api[0](json=payload)
    assert response.status_code == 400
    assert len(events(capsys)) == 1


def test_malformed_json_routes_methods_and_generated_id(api, capsys):
    call, _ = api
    bad = call(data="{", content_type="application/json")
    unknown = call("/arbitrary-unbounded-id", "GET")
    method = call("/orders", "DELETE")
    assert [r.status_code for r in (bad, unknown, method)] == [400, 404, 405]
    assert method.headers["Allow"] == "POST"
    assert all(r.json["request_id"] == r.headers["X-Request-ID"] for r in (bad, unknown, method))
    assert len(events(capsys)) == 3


def test_failure_injection_preserves_client_errors_and_never_writes(
    api, payload, monkeypatch, capsys
):
    call, repository = api
    active = call(json=payload).json["order"]["id"]
    old = call(json=payload).json["order"]["id"]
    call(f"/orders/{old}/cancel")
    events(capsys)
    monkeypatch.setattr(main, "SETTINGS", main.Settings(1, 0))
    assert call(json=payload).status_code == 500
    assert call(f"/orders/{active}/cancel").status_code == 500
    assert repository.get("unscoped", active)["status"] == "created"
    assert len(repository.items) == 2
    assert call(json={}).status_code == 400
    assert call("/orders/missing", "GET").status_code == 404
    assert call(f"/orders/{old}/cancel").status_code == 409
    logs = events(capsys)
    assert [item["error_type"] for item in logs] == [
        "simulated_failure",
        "simulated_failure",
        "invalid_payload",
        "not_found",
        "invalid_state",
    ]


def test_probability_boundary(api, payload, monkeypatch):
    monkeypatch.setattr(main, "SETTINGS", main.Settings(0.02, 0))
    monkeypatch.setattr(main.random, "random", lambda: 0.0199)
    assert api[0](json=payload).status_code == 500
    monkeypatch.setattr(main.random, "random", lambda: 0.02)
    assert api[0](json=payload).status_code == 201


def test_large_finite_numeric_amount_is_normalized_for_firestore(api, payload):
    response = api[0](json={**payload, "amount": 10**100})
    assert response.status_code == 201
    assert type(response.json["order"]["amount"]) is float
    assert response.json["order"]["amount"] == 1e100


def test_latency_and_internal_exception(api, monkeypatch, capsys):
    monkeypatch.setattr(main, "SETTINGS", main.Settings(0, 25))
    assert api[0](json={}).status_code == 400
    assert events(capsys)[0]["latency_ms"] >= 24

    def broken():
        raise RuntimeError("SECRET credential text")

    monkeypatch.setattr(main, "get_repository", broken)
    response = api[0]("/orders/id", "GET")
    assert response.status_code == 500
    assert "SECRET" not in response.get_data(as_text=True)
    logs = events(capsys)
    assert len(logs) == 1
    assert logs[0]["exception_class"] == "RuntimeError"
    assert "SECRET" not in json.dumps(logs)


def test_metadata_resource_wins_and_runs_isolate(api, payload, capsys):
    call, _ = api
    order_id = call(json=payload).json["order"]["id"]
    call(f"/orders/{order_id}", "GET", headers={"X-Lab-Category": "electronics"})
    assert events(capsys)[1]["category"] == "books"
    assert call(f"/orders/{order_id}", "GET", headers={"X-Lab-Run-ID": "other"}).status_code == 404
    assert call(headers={"X-Lab-Run-ID": "invalid/path"}, json=payload).status_code == 400


def test_concurrent_cancels_http(api, payload):
    call, _ = api
    order_id = call(json=payload).json["order"]["id"]
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: call(f"/orders/{order_id}/cancel").status_code, range(2)))
    assert sorted(results) == [200, 409]


@pytest.mark.parametrize(
    "name,value",
    [
        ("FAILURE_RATE", "-1"),
        ("FAILURE_RATE", "2"),
        ("FAILURE_RATE", "nan"),
        ("FAILURE_RATE", "abc"),
        ("EXTRA_LATENCY_MS", "-1"),
        ("EXTRA_LATENCY_MS", "inf"),
    ],
)
def test_bad_environment(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        main.Settings.from_env()
