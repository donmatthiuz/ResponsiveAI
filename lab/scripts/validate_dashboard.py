"""Valida campos/tipos/enums usando el discovery REST oficial versionado."""

import argparse
import json
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[1] / "observability/schema/monitoring-dashboard-v1.json"


def validate_dashboard(dashboard):
    schemas = json.loads(SCHEMA.read_text())["schemas"]

    def check(value, schema, path):
        if "$ref" in schema:
            schema = schemas[schema["$ref"]]
        kind = schema.get("type")
        if kind == "object":
            if not isinstance(value, dict):
                raise ValueError(f"{path}: se requiere objeto")
            properties = schema.get("properties", {})
            for key, item in value.items():
                child = properties.get(key, schema.get("additionalProperties"))
                if not child:
                    raise ValueError(f"{path}.{key}: campo no admitido por REST")
                check(item, child, f"{path}.{key}")
        elif kind == "array":
            if not isinstance(value, list):
                raise ValueError(f"{path}: se requiere lista")
            for index, item in enumerate(value):
                check(item, schema["items"], f"{path}[{index}]")
        else:
            int64 = schema.get("format") in ("int64", "uint64") and type(value) is int
            valid_type = {
                "string": isinstance(value, str) or int64,
                "integer": type(value) is int,
                "number": type(value) in (int, float),
                "boolean": type(value) is bool,
            }.get(kind, True)
            if not valid_type or ("enum" in schema and value not in schema["enum"]):
                raise ValueError(f"{path}: tipo o enum no admitido")

    check(dashboard, schemas["Dashboard"], "Dashboard")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dashboard", type=Path)
    args = parser.parse_args()
    validate_dashboard(json.loads(args.dashboard.read_text()))
    print("Dashboard válido contra discovery REST; requiere comprobación de ingestión en GCP.")
