"""Figuras reproducibles del reporte: solo CSV y logs oficiales, sin tráfico HTTP."""

import argparse
import csv
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def build(directory):
    summary = json.loads((directory / "summary.json").read_text())
    analysis = json.loads((directory / "analysis.json").read_text())
    with (directory / "requests.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    target = directory / "figures"
    target.mkdir(exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.titlesize": 14,
            "axes.labelsize": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )

    def save(fig, name):
        fig.savefig(target / f"{name}.png", dpi=170, bbox_inches="tight")
        fig.savefig(target / f"{name}.svg", bbox_inches="tight")
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 4.2), layout="constrained")
    bottom = np.zeros(60)
    for group, color in [(2, "#3478A2"), (4, "#E8A042"), (5, "#B64D57")]:
        counts = np.zeros(60)
        for row in rows:
            if row["status_code"] and int(row["status_code"]) // 100 == group:
                counts[min(59, int(float(row["scheduled_offset_s"]) / 60))] += 1
        ax.bar(
            np.arange(60) + 0.5, counts, width=0.9, bottom=bottom, color=color, label=f"{group}xx"
        )
        bottom += counts
    mu, sigma = summary["config"]["mu_min"], summary["config"]["sigma_min"]

    def cdf(x):
        return 0.5 * (1 + math.erf((x - mu) / (sigma * math.sqrt(2))))

    norm = cdf(60) - cdf(0)
    expected = [len(rows) * (cdf(i + 1) - cdf(i)) / norm for i in range(60)]
    ax.plot(
        np.arange(60) + 0.5,
        expected,
        color="#253347",
        ls="--",
        lw=1.7,
        label="Conteo esperado: normal truncada",
    )
    ax.axvspan(35, 45, color="#78569C", alpha=0.09, label="Ventana del escenario")
    ax.set(
        xlim=(0, 60),
        xlabel="Minuto programado desde t0",
        ylabel="Solicitudes por minuto",
        title="6000 intentos oficiales; preparación excluida",
    )
    ax.legend(ncol=3, fontsize=9, loc="upper left")
    ax.grid(axis="y", alpha=0.18)
    save(fig, "trafico_oficial")

    fig, ax = plt.subplots(figsize=(10, 4), layout="constrained")
    categories = ["books", "clothing", "electronics"]
    for period, offset, color, label in [
        ("baseline", -0.19, "#3478A2", "Fuera de [35,45)"),
        ("scenario_window", 0.19, "#E8A042", "Dentro de [35,45)"),
    ]:
        subset = [
            next(
                item
                for item in analysis["category_rates"]
                if item["category"] == category and item["period"] == period
            )
            for category in categories
        ]
        values = [item["client_error_rate_http"] * 100 for item in subset]
        positions = np.arange(3) + offset
        ax.bar(positions, values, width=0.35, color=color, label=label)
        for x, value, item in zip(positions, values, subset, strict=True):
            ax.text(
                x,
                value + 0.4,
                f"{value:.2f}%\n{item['client_errors']}/{item['attempts']}",
                ha="center",
                va="bottom",
                fontsize=10,
            )
    ax.set(
        xticks=np.arange(3),
        xticklabels=categories,
        ylim=(0, 22),
        ylabel="Respuestas 4xx / respuestas HTTP (%)",
        title="El escenario modifica electronics; los conteos son frecuencias observadas",
    )
    ax.legend(loc="upper left", fontsize=10)
    ax.grid(axis="y", alpha=0.18)
    save(fig, "errores_por_categoria")

    fig, ax = plt.subplots(figsize=(11, 4.2), layout="constrained")
    data = []
    for operation, endpoint, label in [
        ("create", "POST /orders", "Crear"),
        ("get", "GET /orders/{id}", "Consultar"),
        ("cancel", "POST /orders/{id}/cancel", "Cancelar"),
    ]:
        for tier in ["standard", "premium"]:
            client = analysis["client_latency_by_operation_tier"][f"{operation} / {tier}"]["p95"]
            backend = analysis["backend_latency_by_endpoint_tier"][f"{endpoint} / {tier}"]["p95"]
            data.append((f"{label}\n{tier}", client, backend))
    positions = np.arange(len(data))
    ax.bar(positions - 0.19, [item[1] for item in data], 0.36, label="Cliente", color="#3478A2")
    ax.bar(positions + 0.19, [item[2] for item in data], 0.36, label="Backend", color="#43A491")
    ax.set(
        xticks=positions,
        xticklabels=[item[0] for item in data],
        ylabel="Latencia p95 (ms)",
        title="Percentiles empíricos de la corrida completa, por operación y segmento",
    )
    ax.legend(loc="upper left")
    ax.grid(axis="y", alpha=0.18)
    save(fig, "latencia_p95")
    print(f"Generadas tres figuras PNG/SVG en {target}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_dir", type=Path)
    build(parser.parse_args().evidence_dir)
