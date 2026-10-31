import asyncio
import csv
import json
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

import simulator.simulator as simulator_module
from simulator.simulator import (
    Event,
    TokenProvider,
    build_plan,
    dispatch,
    effective_invalid_share,
    prepare,
    run,
    validate_config,
)


@pytest.fixture
def config():
    return json.loads((Path(__file__).parents[1] / "simulator/config.json").read_text())


def test_reproducible_truncated_schedule_and_resource_reservations(config):
    plan = build_plan(config, "test")
    assert plan == build_plan(config, "test")
    assert len(plan) == 6000
    offsets = [event.scheduled_offset_s for event in plan]
    assert offsets == sorted(offsets)
    assert all(0 <= value <= 3600 for value in offsets)
    assert all(value not in (0, 3600) for value in offsets)
    assert len({event.request_id for event in plan}) == 6000
    cancel_keys = [
        event.resource_key
        for event in plan
        if event.operation == "cancel" and event.intended_event == "valid"
    ]
    assert len(cancel_keys) == len(set(cancel_keys))
    assert {event.intended_event for event in plan} == {
        "valid",
        "invalid_payload",
        "not_found",
        "invalid_state",
    }


@pytest.mark.parametrize(
    "minute,category,expected",
    [
        (34.999, "electronics", 0.08),
        (35, "electronics", 0.16),
        (44.999, "electronics", 0.16),
        (45, "electronics", 0.08),
        (40, "books", 0.08),
    ],
)
def test_scenario_boundaries(config, minute, category, expected):
    assert effective_invalid_share(config, minute, category)[0] == expected


def test_scenario_reads_config_and_caps_probability(config):
    config["invalid_share"] = 0.7
    config["scenarios"] = [
        {"category": "books", "effect": "double_errors", "start_min": 10, "end_min": 20}
    ]
    assert effective_invalid_share(config, 10, "books")[0] == 1
    assert effective_invalid_share(config, 40, "electronics")[0] == 0.7


@pytest.mark.parametrize(
    "key,value",
    [
        ("n_requests", 0),
        ("n_requests", True),
        ("target_url", "invalid"),
        ("target_url", "https://user:secret@example.com"),
        ("target_url", "https://example.com:invalid"),
        ("sigma_min", 0),
        ("sigma_min", float("nan")),
        ("invalid_share", 2),
        ("invalid_share", True),
        ("seed", -1),
        ("mu_min", -2),
        (
            "scenarios",
            [{"start_min": 1, "end_min": 2, "category": "books", "effect": "unsupported"}],
        ),
        (
            "scenarios",
            [{"start_min": 2, "end_min": 1, "category": "books", "effect": "double_errors"}],
        ),
    ],
)
def test_invalid_config(config, key, value):
    with pytest.raises(ValueError):
        validate_config({**config, key: value})


def test_overlapping_scenarios(config):
    config["scenarios"] *= 2
    with pytest.raises(ValueError, match="superpuestos"):
        validate_config(config)


async def test_dry_run_without_network_and_no_overwrite(config, tmp_path):
    out = tmp_path / "requests.csv"
    summary = await run(config, out, "dry", dry_run=True)
    assert summary["sent"] == 0 and summary["programmed"] == 6000
    assert not out.exists()
    assert len(list(csv.DictReader((tmp_path / "schedule.csv").open()))) == 6000
    with pytest.raises(ValueError, match="sobrescribe"):
        await run(config, out, "dry", dry_run=True)


def simple_event(index, offset):
    return Event(
        f"test-{index}", offset, "create", "valid", 201, "books", "premium", 10, "baseline", ""
    )


async def test_dispatch_concurrent_slow_server_and_csv_transport_failure(config, tmp_path):
    started, ended = {}, {}

    async def slow(request):
        request_id = request.headers["X-Request-ID"]
        started[request_id] = time.monotonic()
        await asyncio.sleep(0.08)
        ended[request_id] = time.monotonic()
        if request_id == "test-2":
            raise httpx.ConnectError("test connection failure")
        return httpx.Response(201, json={"order": {"id": request_id}})

    plan = [simple_event(i, i * 10) for i in range(3)]
    async with httpx.AsyncClient(transport=httpx.MockTransport(slow)) as client:
        summary = await dispatch(
            client, config, plan, {}, "test", tmp_path / "requests.csv", 0.00005, TokenProvider()
        )
    assert started["test-1"] < ended["test-0"]
    assert summary["status"] == "complete"
    assert summary["execution_kind"] == "accelerated_test"
    assert summary["sent"] == summary["completed"] == 3
    rows = list(csv.DictReader((tmp_path / "requests.csv").open()))
    assert len(rows) == 3
    error = next(row for row in rows if row["request_id"] == "test-2")
    assert error["status_code"] == "" and "ConnectError" in error["transport_error"]
    assert all(float(row["dispatch_delay_ms"]) >= 0 for row in rows)


async def test_partial_csv_and_incomplete_summary_survive_cancellation(config, tmp_path):
    async def slow(request):
        await asyncio.sleep(0.5)
        return httpx.Response(201)

    async with httpx.AsyncClient(transport=httpx.MockTransport(slow)) as client:
        task = asyncio.create_task(
            dispatch(
                client,
                config,
                [simple_event(0, 0), simple_event(1, 3500)],
                {},
                "partial",
                tmp_path / "requests.csv",
                0.001,
                TokenProvider(),
            )
        )
        await asyncio.sleep(0.15)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    rows = list(csv.DictReader((tmp_path / "requests.csv").open()))
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert len(rows) == 1 and rows[0]["transport_error"] == "cancelled"
    assert summary["status"] == "incomplete" and summary["sent"] == 1


async def test_suspended_host_does_not_send_after_window(config, tmp_path, monkeypatch):
    clock = [100.0]
    actual_sleep = asyncio.sleep
    auth = TokenProvider()

    async def suspended_sleep(delay):
        clock[0] += 3601
        await actual_sleep(0)

    monkeypatch.setattr(simulator_module, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(
        simulator_module,
        "asyncio",
        SimpleNamespace(
            sleep=suspended_sleep, create_task=asyncio.create_task, gather=asyncio.gather
        ),
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(201))
    ) as client:
        summary = await dispatch(
            client,
            config,
            [simple_event(0, 1)],
            {},
            "suspended",
            tmp_path / "requests.csv",
            1,
            auth,
        )
    assert summary["status"] == "incomplete"
    assert summary["incomplete_reason"] == "send_window_expired"
    assert summary["sent"] == 0


async def test_preparation_retries_and_distinct_resources(config, tmp_path):
    attempts = 0

    async def prepare_handler(request):
        nonlocal attempts
        assert request.headers["X-Lab-Phase"] == "preparation"
        attempts += 1
        if attempts == 1:
            return httpx.Response(500)
        return httpx.Response(201, json={"order": {"id": str(attempts)}})

    plan = [
        replace(simple_event(i, i), operation="cancel", resource_key=f"cancel:{i}")
        for i in range(2)
    ]
    async with httpx.AsyncClient(transport=httpx.MockTransport(prepare_handler)) as client:
        prepared = await prepare(client, config, plan, "prep", tmp_path, TokenProvider())
    assert len(prepared) == len(set(prepared.values())) == 2
    assert attempts == 3
    assert (tmp_path / "preparation.jsonl").exists()


@pytest.mark.parametrize("code,expected_attempts", [(500, 3), (403, 1)])
async def test_preparation_stops_before_traffic_on_failure(
    config, tmp_path, code, expected_attempts
):
    calls = []

    def failed(request):
        calls.append(request)
        return httpx.Response(code)

    # Crear exactamente un recurso requerido para no mezclar reintentos entre recursos.
    config.update(n_requests=1, seed=1, invalid_share=0)
    while build_plan(config, "failure")[0].operation == "create":
        config["seed"] += 1
    with pytest.raises(ExceptionGroup):
        await run(
            config, tmp_path / "requests.csv", "failure", transport=httpx.MockTransport(failed)
        )
    assert len(calls) == expected_attempts
    assert not (tmp_path / "requests.csv").exists()
    assert json.loads((tmp_path / "summary.json").read_text())["status"] == "preparation_failed"
