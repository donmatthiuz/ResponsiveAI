import json
from pathlib import Path

from google.cloud.monitoring_dashboard_v1.types import Dashboard

from scripts.render_observability import render
from scripts.validate_dashboard import validate_dashboard


def test_dashboard_matches_official_proto_schema_and_sql_filters():
    summary = {
        "run_id": "official-42",
        "window_start_utc": "2026-10-30T20:00:00+00:00",
        "finished_at_utc": "2026-10-30T21:01:00+00:00",
    }
    dashboard, queries = render("demo-observable-lab", "orders-api", summary, "request-123")
    # REST incluye preview SQL; el SDK estable aún no representa esos campos.
    validate_dashboard(dashboard)
    stable = json.loads(json.dumps(dashboard))
    stable["gridLayout"]["widgets"] = [
        widget
        for widget in stable["gridLayout"]["widgets"]
        if not any(
            "opsAnalyticsQuery" in dataset["timeSeriesQuery"]
            for dataset in widget.get("xyChart", {}).get("dataSets", [])
        )
    ]
    parsed = Dashboard.from_json(json.dumps(stable), ignore_unknown_fields=False)
    assert len(parsed.grid_layout.widgets) == 6
    assert len(dashboard["gridLayout"]["widgets"]) == 8
    assert (
        len([widget for widget in dashboard["gridLayout"]["widgets"] if "logsPanel" in widget]) == 1
    )
    for query in queries.values():
        assert "'official-42'" in query and "'traffic'" in query
        assert "__" not in query
        assert "2026-10-30T20:00:00+00:00" in query
    assert "SAFE_DIVIDE" in queries["errors_by_category.sql"]
    assert "SAFE_CAST" in queries["latency_by_tier.sql"]


def test_template_remains_json():
    path = Path(__file__).parents[1] / "observability/dashboard.json"
    assert json.loads(path.read_text())["displayName"]


def test_sql_chart_configuration_matches_verified_console_export():
    root = Path(__file__).parents[1]
    reference = json.loads((root / "tests/fixtures/sql_chart_verified.json").read_text())
    dashboard = json.loads((root / "observability/dashboard.json").read_text())
    sql_widgets = [
        widget
        for widget in dashboard["gridLayout"]["widgets"]
        if any(
            "opsAnalyticsQuery" in dataset["timeSeriesQuery"]
            for dataset in widget.get("xyChart", {}).get("dataSets", [])
        )
    ]
    assert len(sql_widgets) == 2
    for widget in sql_widgets:
        assert widget["xyChart"]["chartOptions"] == reference["chartOptions"]
        assert len(widget["xyChart"]["dataSets"]) == 1
        for dataset in widget["xyChart"]["dataSets"]:
            assert len(dataset["measures"]) == len(dataset["breakdowns"]) == 1
            assert dataset["dimensions"] == reference["dimensions"]
            assert (
                dataset["measures"][0]["aggregationFunction"]
                == reference["measure"]["aggregationFunction"]
            )
            for breakdown in dataset["breakdowns"]:
                assert (
                    breakdown["aggregationFunction"]
                    == reference["breakdown"]["aggregationFunction"]
                )
                assert breakdown["sortOrder"] == reference["breakdown"]["sortOrder"]
                assert breakdown["limit"] > 0
    error_series = sql_widgets[0]["xyChart"]["dataSets"][0]
    assert error_series["breakdowns"] == [reference["breakdown"]]
    latency_series = sql_widgets[1]["xyChart"]["dataSets"]
    assert latency_series[0]["measures"][0]["column"] == "latency_ms"
    assert latency_series[0]["breakdowns"][0]["column"] == "series"
    sql = (root / "observability/queries/latency_by_tier.sql").read_text()
    assert "'p50' AS percentile" in sql and "'p95' AS percentile" in sql


def test_render_preserves_verified_manual_widget_when_retargeting_owned_sql():
    root = Path(__file__).parents[1]
    reference = json.loads((root / "tests/fixtures/sql_chart_verified.json").read_text())
    old_summary = {
        "run_id": "smoke-old",
        "window_start_utc": "2026-10-31T02:00:00Z",
        "finished_at_utc": "2026-10-31T02:01:00Z",
    }
    original, _ = render("demo-observable-lab", "orders-api", old_summary)
    original["gridLayout"]["widgets"].append(reference["widget"])
    snapshot = json.dumps(original)
    new_summary = {
        "run_id": "official-new",
        "window_start_utc": "2026-10-31T03:00:00Z",
        "finished_at_utc": "2026-10-31T04:00:00Z",
    }
    updated, _ = render("demo-observable-lab", "orders-api", new_summary, source=original)
    validate_dashboard(updated)
    assert json.dumps(original) == snapshot
    before, after = original["gridLayout"]["widgets"], updated["gridLayout"]["widgets"]
    assert [widget["title"] for widget in before] == [widget["title"] for widget in after]
    for index in (0, 1, 2, 3, 6, 8):
        assert before[index] == after[index]
    for index in (4, 5):
        for old, new in zip(
            before[index]["xyChart"]["dataSets"], after[index]["xyChart"]["dataSets"], strict=True
        ):
            assert "'smoke-old'" in old["timeSeriesQuery"]["opsAnalyticsQuery"]["sql"]
            assert "'official-new'" in new["timeSeriesQuery"]["opsAnalyticsQuery"]["sql"]


def test_render_migrates_legacy_latency_chart_without_changing_manual_widget():
    root = Path(__file__).parents[1]
    reference = json.loads((root / "tests/fixtures/sql_chart_verified.json").read_text())
    summary = {
        "run_id": "smoke-migration",
        "window_start_utc": "2026-10-31T02:00:00Z",
        "finished_at_utc": "2026-10-31T02:01:00Z",
    }
    source, _ = render("demo-observable-lab", "orders-api", summary)
    source["gridLayout"]["widgets"].append(reference["widget"])
    latency = source["gridLayout"]["widgets"][5]["xyChart"]
    legacy = json.loads(json.dumps(latency["dataSets"][0]))
    legacy["breakdowns"] = [{"column": "customer_tier"}, {"column": "endpoint"}]
    latency["dataSets"] = [json.loads(json.dumps(legacy)) for _ in range(2)]
    for dataset, column in zip(latency["dataSets"], ["p50_ms", "p95_ms"], strict=True):
        dataset["measures"][0]["column"] = column
    snapshot = json.dumps(source)
    updated, _ = render("demo-observable-lab", "orders-api", summary, source=source)
    assert json.dumps(source) == snapshot
    widgets = updated["gridLayout"]["widgets"]
    assert widgets[-1] == reference["widget"]
    assert len(widgets[5]["xyChart"]["dataSets"]) == 1
    assert widgets[5]["xyChart"]["dataSets"][0]["measures"][0]["column"] == "latency_ms"
    assert widgets[5]["xyChart"]["dataSets"][0]["breakdowns"][0]["column"] == "series"
    validate_dashboard(updated)
