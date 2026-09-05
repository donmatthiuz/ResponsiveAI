"""Experimento reproducible de clasificación de dígitos y explicaciones TreeSHAP.

Este archivo es la fuente canónica de todos los resultados numéricos y figuras
incluidos en ``paper.tex``. No descarga datos: usa ``sklearn.datasets.load_digits``.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import shap
import sklearn
from matplotlib.colors import TwoSlopeNorm
from sklearn.datasets import load_digits
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split


SEED = 42
TEST_SIZE = 0.20
N_TREES = 300
BACKGROUND_PER_CLASS = 10
DELETION_K = (1, 2, 4, 8)
RANDOM_REPEATS_SELECTED = 200
RANDOM_REPEATS_GLOBAL = 100
BOOTSTRAP_REPEATS = 2_000


@dataclass(frozen=True)
class SelectedCase:
    order: int
    criterion: str
    test_position: int
    dataset_index: int
    true_class: int
    predicted_class: int
    comparison_class: int
    confidence: float
    margin: float
    correct: bool


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _json_ready(value: Any) -> Any:
    """Convierte tipos NumPy/Path a tipos serializables."""
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(_json_ready(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _save_figure(fig: plt.Figure, figures_dir: Path, stem: str) -> None:
    fig.savefig(figures_dir / f"{stem}.png", dpi=220, bbox_inches="tight")
    fig.savefig(figures_dir / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)


def _configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "figure.titlesize": 12,
            "savefig.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def _stratified_background(
    X_train: np.ndarray, y_train: np.ndarray, per_class: int, seed: int
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    selected: list[int] = []
    for class_id in np.unique(y_train):
        positions = np.flatnonzero(y_train == class_id)
        if len(positions) < per_class:
            raise ValueError(f"No hay {per_class} muestras para la clase {class_id}.")
        selected.extend(rng.choice(positions, size=per_class, replace=False).tolist())
    return X_train[np.asarray(selected, dtype=int)]


def _normalize_shap_values(
    raw_values: Any, n_samples: int, n_features: int, n_classes: int
) -> np.ndarray:
    """Normaliza APIs históricas de SHAP a (muestras, atributos, clases)."""
    if isinstance(raw_values, list):
        values = np.stack([np.asarray(item) for item in raw_values], axis=-1)
    else:
        values = np.asarray(raw_values)

    expected_shape = (n_samples, n_features, n_classes)
    if values.shape == expected_shape:
        return values.astype(float, copy=False)
    if values.shape == (n_samples, n_classes, n_features):
        return np.transpose(values, (0, 2, 1)).astype(float, copy=False)
    if n_samples == 1 and values.shape == (n_features, n_classes):
        return values[np.newaxis, ...].astype(float, copy=False)
    raise ValueError(
        f"Forma SHAP inesperada {values.shape}; se esperaba {expected_shape}."
    )


def _explain(
    explainer: shap.TreeExplainer,
    X: np.ndarray,
    n_classes: int,
) -> np.ndarray:
    explanation = explainer(X, check_additivity=False)
    return _normalize_shap_values(
        explanation.values,
        n_samples=X.shape[0],
        n_features=X.shape[1],
        n_classes=n_classes,
    )


def _select_cases(
    y_test: np.ndarray,
    predictions: np.ndarray,
    probabilities: np.ndarray,
    test_indices: np.ndarray,
) -> list[SelectedCase]:
    def choose_min(candidates: np.ndarray, scores: np.ndarray) -> int:
        """Minimiza score y desempata por el menor índice del dataset original."""
        best_score = float(np.min(scores[candidates]))
        tied = candidates[
            np.isclose(scores[candidates], best_score, rtol=0.0, atol=1e-12)
        ]
        return int(tied[np.argmin(test_indices[tied])])

    def choose_max(candidates: np.ndarray, scores: np.ndarray) -> int:
        return choose_min(candidates, -scores)

    positions = np.arange(len(y_test))
    confidence = probabilities[positions, predictions]
    sorted_probability = np.sort(probabilities, axis=1)
    margins = sorted_probability[:, -1] - sorted_probability[:, -2]
    correct_positions = positions[predictions == y_test]
    if len(correct_positions) < 3:
        raise RuntimeError("Se necesitan al menos tres aciertos para seleccionar casos.")

    median_confidence = float(np.median(confidence[correct_positions]))
    distance_to_median = np.abs(confidence - median_confidence)
    typical = choose_min(correct_positions, distance_to_median)
    remaining_correct = correct_positions[correct_positions != typical]
    ambiguous = choose_min(remaining_correct, margins)

    error_positions = positions[predictions != y_test]
    if len(error_positions):
        third = choose_max(error_positions, confidence)
        third_criterion = "Error de mayor confianza"
    else:
        candidates = remaining_correct[remaining_correct != ambiguous]
        third = choose_min(candidates, margins)
        third_criterion = "Acierto alternativo de bajo margen"

    specifications = [
        (typical, "Acierto de confianza mediana"),
        (ambiguous, "Acierto correcto de menor margen"),
        (third, third_criterion),
    ]
    cases: list[SelectedCase] = []
    for order, (position, criterion) in enumerate(specifications, start=1):
        ranking = np.argsort(probabilities[position])[::-1]
        prediction = int(predictions[position])
        truth = int(y_test[position])
        if prediction != truth:
            comparison = truth
        else:
            comparison = int(next(label for label in ranking if label != prediction))
        cases.append(
            SelectedCase(
                order=order,
                criterion=criterion,
                test_position=int(position),
                dataset_index=int(test_indices[position]),
                true_class=truth,
                predicted_class=prediction,
                comparison_class=comparison,
                confidence=float(confidence[position]),
                margin=float(margins[position]),
                correct=bool(prediction == truth),
            )
        )
    return cases


def _mask_features(
    sample: np.ndarray, feature_indices: np.ndarray, replacement: np.ndarray
) -> np.ndarray:
    masked = sample.copy()
    masked[feature_indices] = replacement[feature_indices]
    return masked


def _selected_deletion_test(
    model: RandomForestClassifier,
    X_selected: np.ndarray,
    cases: list[SelectedCase],
    shap_values: np.ndarray,
    replacement: np.ndarray,
    eligible_random_features: np.ndarray,
    seed: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rng = np.random.default_rng(seed)
    if len(eligible_random_features) < max(DELETION_K):
        raise ValueError("El universo del control aleatorio tiene menos de 8 píxeles.")

    for local_index, case in enumerate(cases):
        target_class = case.predicted_class
        sample = X_selected[local_index]
        original_probability = float(model.predict_proba(sample[None, :])[0, target_class])
        attribution = shap_values[local_index, :, target_class]
        ranking = np.argsort(-attribution)
        if np.any(attribution[ranking[: max(DELETION_K)]] <= 0):
            raise AssertionError("Uno de los ocho píxeles SHAP seleccionados no es positivo.")
        if not np.all(np.isin(ranking[: max(DELETION_K)], eligible_random_features)):
            raise AssertionError("SHAP seleccionó un píxel fuera del universo variable.")

        rows.append(
            {
                "case": case.order,
                "criterion": case.criterion,
                "k": 0,
                "predicted_class": target_class,
                "original_probability": original_probability,
                "shap_probability": original_probability,
                "shap_drop": 0.0,
                "random_probability_mean": original_probability,
                "random_probability_low": original_probability,
                "random_probability_high": original_probability,
                "random_drop_mean": 0.0,
                "random_candidate_features": int(len(eligible_random_features)),
            }
        )

        for k in DELETION_K:
            top_features = ranking[:k]
            shap_masked = _mask_features(sample, top_features, replacement)
            shap_probability = float(
                model.predict_proba(shap_masked[None, :])[0, target_class]
            )

            random_masks = np.repeat(sample[None, :], RANDOM_REPEATS_SELECTED, axis=0)
            for repeat in range(RANDOM_REPEATS_SELECTED):
                random_features = rng.choice(
                    eligible_random_features, size=k, replace=False
                )
                random_masks[repeat, random_features] = replacement[random_features]
            random_probability = model.predict_proba(random_masks)[:, target_class]

            rows.append(
                {
                    "case": case.order,
                    "criterion": case.criterion,
                    "k": k,
                    "predicted_class": target_class,
                    "original_probability": original_probability,
                    "shap_probability": float(shap_probability),
                    "shap_drop": float(original_probability - shap_probability),
                    "random_probability_mean": float(np.mean(random_probability)),
                    "random_probability_low": float(np.quantile(random_probability, 0.025)),
                    "random_probability_high": float(np.quantile(random_probability, 0.975)),
                    "random_drop_mean": float(
                        original_probability - np.mean(random_probability)
                    ),
                    "random_candidate_features": int(len(eligible_random_features)),
                }
            )
    return rows


def _global_deletion_test(
    model: RandomForestClassifier,
    X_correct: np.ndarray,
    predicted_classes: np.ndarray,
    probabilities: np.ndarray,
    shap_values: np.ndarray,
    replacement: np.ndarray,
    eligible_random_features: np.ndarray,
    seed: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    n_samples, _ = X_correct.shape
    sample_ids = np.arange(n_samples)
    original = probabilities[sample_ids, predicted_classes]

    selected_class_values = shap_values[sample_ids, :, predicted_classes]
    positive_counts = np.sum(selected_class_values > 0, axis=1)
    if int(np.min(positive_counts)) < 8:
        raise AssertionError("Algún acierto tiene menos de ocho atribuciones positivas.")
    rankings = np.argsort(-selected_class_values, axis=1)[:, :8]
    if not np.all(np.isin(rankings, eligible_random_features)):
        raise AssertionError("SHAP seleccionó un píxel fuera del universo variable.")
    shap_masked = X_correct.copy()
    for row in range(n_samples):
        shap_masked[row, rankings[row]] = replacement[rankings[row]]
    after_shap = model.predict_proba(shap_masked)[sample_ids, predicted_classes]
    shap_drop = original - after_shap

    rng = np.random.default_rng(seed)
    random_drops = np.empty((RANDOM_REPEATS_GLOBAL, n_samples), dtype=float)
    for repeat in range(RANDOM_REPEATS_GLOBAL):
        random_masked = X_correct.copy()
        for row in range(n_samples):
            chosen = rng.choice(eligible_random_features, size=8, replace=False)
            random_masked[row, chosen] = replacement[chosen]
        after_random = model.predict_proba(random_masked)[sample_ids, predicted_classes]
        random_drops[repeat] = original - after_random

    random_drop_mean = np.mean(random_drops, axis=0)
    paired_difference = shap_drop - random_drop_mean

    bootstrap_rng = np.random.default_rng(seed + 1)
    bootstrap_medians = np.empty(BOOTSTRAP_REPEATS, dtype=float)
    for repeat in range(BOOTSTRAP_REPEATS):
        sampled = bootstrap_rng.integers(0, n_samples, size=n_samples)
        bootstrap_medians[repeat] = np.median(paired_difference[sampled])

    rows = [
        {
            "correct_case_number": int(row + 1),
            "predicted_class": int(predicted_classes[row]),
            "original_probability": float(original[row]),
            "shap_drop_at_8": float(shap_drop[row]),
            "random_mean_drop_at_8": float(random_drop_mean[row]),
            "paired_difference": float(paired_difference[row]),
        }
        for row in range(n_samples)
    ]
    summary = {
        "n_correct_cases": int(n_samples),
        "k": 8,
        "random_repeats_per_case": RANDOM_REPEATS_GLOBAL,
        "random_candidate_features": int(len(eligible_random_features)),
        "minimum_positive_attributions_per_case": int(np.min(positive_counts)),
        "median_shap_drop": float(np.median(shap_drop)),
        "median_random_mean_drop": float(np.median(random_drop_mean)),
        "median_paired_difference": float(np.median(paired_difference)),
        "paired_difference_bootstrap_ci_95": [
            float(np.quantile(bootstrap_medians, 0.025)),
            float(np.quantile(bootstrap_medians, 0.975)),
        ],
        "fraction_shap_drop_greater_than_random_mean": float(
            np.mean(shap_drop > random_drop_mean)
        ),
    }
    return rows, summary


def _plot_dataset_examples(
    images: np.ndarray, labels: np.ndarray, figures_dir: Path
) -> None:
    fig, axes = plt.subplots(2, 5, figsize=(8.2, 3.6))
    for class_id, axis in enumerate(axes.flat):
        position = int(np.flatnonzero(labels == class_id)[0])
        axis.imshow(images[position], cmap="gray_r", vmin=0, vmax=16)
        axis.set_title(f"Clase {class_id}")
        axis.axis("off")
    fig.suptitle("Ejemplo determinista de cada clase del conjunto digits")
    fig.tight_layout()
    _save_figure(fig, figures_dir, "dataset_examples")


def _plot_confusion_matrix(matrix: np.ndarray, figures_dir: Path) -> None:
    fig, axis = plt.subplots(figsize=(5.4, 4.7))
    image = axis.imshow(matrix, cmap="Blues")
    axis.set(
        xlabel="Clase predicha",
        ylabel="Clase verdadera",
        xticks=np.arange(10),
        yticks=np.arange(10),
        title="Matriz de confusión en el conjunto de prueba",
    )
    threshold = matrix.max() / 2
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            axis.text(
                column,
                row,
                str(matrix[row, column]),
                ha="center",
                va="center",
                color="white" if matrix[row, column] > threshold else "black",
                fontsize=8,
            )
    fig.colorbar(image, ax=axis, fraction=0.046, pad=0.04, label="Número de imágenes")
    fig.tight_layout()
    _save_figure(fig, figures_dir, "confusion_matrix")


def _plot_shap_explanations(
    X_selected: np.ndarray,
    cases: list[SelectedCase],
    shap_values: np.ndarray,
    probabilities: np.ndarray,
    figures_dir: Path,
) -> None:
    fig, axes = plt.subplots(len(cases), 3, figsize=(10.6, 9.0))
    all_maps: list[np.ndarray] = []
    for local_index, case in enumerate(cases):
        all_maps.extend(
            [
                shap_values[local_index, :, case.predicted_class],
                shap_values[local_index, :, case.comparison_class],
            ]
        )
    limit = max(float(np.max(np.abs(values))) for values in all_maps)
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)
    heatmap = None

    for row, case in enumerate(cases):
        image = X_selected[row].reshape(8, 8)
        axes[row, 0].imshow(image, cmap="gray_r", vmin=0, vmax=16)
        state = "correcto" if case.correct else "error"
        axes[row, 0].set_title(
            f"Caso {case.order}: y={case.true_class}, ŷ={case.predicted_class}\n"
            f"p(ŷ)={case.confidence:.3f}; {state}"
        )
        axes[row, 0].axis("off")

        predicted_map = shap_values[row, :, case.predicted_class].reshape(8, 8)
        heatmap = axes[row, 1].imshow(predicted_map, cmap="RdBu_r", norm=norm)
        axes[row, 1].set_title(
            f"SHAP para clase predicha {case.predicted_class}"
        )
        axes[row, 1].set_xticks([])
        axes[row, 1].set_yticks([])

        comparison_map = shap_values[row, :, case.comparison_class].reshape(8, 8)
        axes[row, 2].imshow(comparison_map, cmap="RdBu_r", norm=norm)
        comparison_label = "verdadera" if not case.correct else "segunda opción"
        comparison_probability = probabilities[
            case.test_position, case.comparison_class
        ]
        axes[row, 2].set_title(
            f"Clase {comparison_label} {case.comparison_class}\n"
            f"p={comparison_probability:.3f}"
        )
        axes[row, 2].set_xticks([])
        axes[row, 2].set_yticks([])

    fig.subplots_adjust(top=0.91, right=0.88, hspace=0.38, wspace=0.18)
    if heatmap is not None:
        colorbar_axis = fig.add_axes([0.91, 0.19, 0.018, 0.62])
        colorbar = fig.colorbar(heatmap, cax=colorbar_axis)
        colorbar.set_label("Valor SHAP (rojo: apoyo; azul: oposición)")
    fig.suptitle("Explicaciones locales respecto al fondo estratificado")
    _save_figure(fig, figures_dir, "shap_explanations")


def _plot_selected_deletion(
    rows: list[dict[str, Any]], cases: list[SelectedCase], figures_dir: Path
) -> None:
    fig, axes = plt.subplots(1, len(cases), figsize=(11.4, 3.6), sharey=True)
    for axis, case in zip(axes, cases):
        case_rows = sorted(
            (row for row in rows if row["case"] == case.order), key=lambda row: row["k"]
        )
        k_values = np.array([row["k"] for row in case_rows])
        shap_probability = np.array([row["shap_probability"] for row in case_rows])
        random_mean = np.array([row["random_probability_mean"] for row in case_rows])
        random_low = np.array([row["random_probability_low"] for row in case_rows])
        random_high = np.array([row["random_probability_high"] for row in case_rows])

        axis.plot(k_values, shap_probability, "o-", color="#C62828", label="Top SHAP")
        axis.plot(k_values, random_mean, "s--", color="#1565C0", label="Azar (media)")
        axis.fill_between(k_values, random_low, random_high, color="#1565C0", alpha=0.16)
        axis.set_title(f"Caso {case.order}: clase {case.predicted_class}")
        axis.set_xlabel("Píxeles sustituidos")
        axis.set_xticks(k_values)
        axis.grid(alpha=0.25)
    axes[0].set_ylabel("Probabilidad de la clase predicha")
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Prueba de eliminación en las tres imágenes seleccionadas")
    fig.tight_layout()
    _save_figure(fig, figures_dir, "deletion_selected")


def _plot_global_deletion(
    rows: list[dict[str, Any]], summary: dict[str, Any], figures_dir: Path
) -> None:
    shap_drop = np.array([row["shap_drop_at_8"] for row in rows])
    random_drop = np.array([row["random_mean_drop_at_8"] for row in rows])
    paired = shap_drop - random_drop

    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.9))
    boxes = axes[0].boxplot(
        [shap_drop, random_drop],
        tick_labels=["Top SHAP", "Azar"],
        patch_artist=True,
        showfliers=True,
    )
    for patch, color in zip(boxes["boxes"], ["#EF9A9A", "#90CAF9"]):
        patch.set_facecolor(color)
    axes[0].axhline(0, color="black", linewidth=0.7)
    axes[0].set_ylabel("Caída de probabilidad al sustituir 8 píxeles")
    axes[0].set_title("Distribución sobre todos los aciertos")
    axes[0].grid(axis="y", alpha=0.25)

    axes[1].hist(paired, bins=24, color="#6A1B9A", alpha=0.78, edgecolor="white")
    axes[1].axvline(0, color="black", linewidth=1, linestyle="--")
    axes[1].axvline(
        summary["median_paired_difference"],
        color="#FF8F00",
        linewidth=2,
        label="Mediana",
    )
    axes[1].set(
        xlabel="Caída SHAP − caída aleatoria media",
        ylabel="Número de casos",
        title="Diferencia emparejada",
    )
    axes[1].grid(axis="y", alpha=0.25)
    axes[1].legend(frameon=False, fontsize=8)
    fig.suptitle("Evaluación global de eliminación (drop@8)")
    fig.tight_layout()
    _save_figure(fig, figures_dir, "deletion_global")


def _export_selected_images(
    X_selected: np.ndarray, cases: list[SelectedCase], figures_dir: Path
) -> None:
    for row, case in enumerate(cases):
        fig, axis = plt.subplots(figsize=(2.0, 2.0))
        axis.imshow(X_selected[row].reshape(8, 8), cmap="gray_r", vmin=0, vmax=16)
        axis.axis("off")
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
        fig.savefig(
            figures_dir / f"test_image_{case.order}.png",
            dpi=128,
            bbox_inches="tight",
            pad_inches=0,
        )
        plt.close(fig)


def _latex_scientific(value: float) -> str:
    if value == 0:
        return "0"
    mantissa, exponent = f"{value:.2e}".split("e")
    return rf"\ensuremath{{{mantissa}\times 10^{{{int(exponent)}}}}}"


def _write_latex_results(
    results_dir: Path,
    metrics: dict[str, Any],
    cases: list[SelectedCase],
    deletion_summary: dict[str, Any],
) -> None:
    performance = metrics["performance"]
    shap_info = metrics["shap"]
    split = metrics["split"]
    ci_low, ci_high = deletion_summary["paired_difference_bootstrap_ci_95"]
    macros = [
        "% Archivo generado automáticamente por src/run_experiment.py.",
        rf"\newcommand{{\DatasetSize}}{{{metrics['dataset']['n_samples']}}}",
        rf"\newcommand{{\TrainSize}}{{{split['n_train']}}}",
        rf"\newcommand{{\TestSizeN}}{{{split['n_test']}}}",
        rf"\newcommand{{\TestAccuracy}}{{{100 * performance['accuracy']:.2f}\%}}",
        rf"\newcommand{{\MacroFOne}}{{{performance['macro_f1']:.3f}}}",
        rf"\newcommand{{\CorrectTestCases}}{{{performance['n_correct']}}}",
        rf"\newcommand{{\IncorrectTestCases}}{{{performance['n_incorrect']}}}",
        rf"\newcommand{{\NumTrees}}{{{metrics['model']['n_estimators']}}}",
        rf"\newcommand{{\BackgroundSize}}{{{shap_info['background_size']}}}",
        rf"\newcommand{{\RandomCandidateFeatures}}{{{deletion_summary['random_candidate_features']}}}",
        rf"\newcommand{{\MaxAdditivityError}}{{{_latex_scientific(shap_info['max_additivity_error'])}}}",
        rf"\newcommand{{\MedianShapDrop}}{{{deletion_summary['median_shap_drop']:.3f}}}",
        rf"\newcommand{{\MedianRandomDrop}}{{{deletion_summary['median_random_mean_drop']:.3f}}}",
        rf"\newcommand{{\MedianPairedDifference}}{{{deletion_summary['median_paired_difference']:.3f}}}",
        rf"\newcommand{{\DeletionCILow}}{{{ci_low:.3f}}}",
        rf"\newcommand{{\DeletionCIHigh}}{{{ci_high:.3f}}}",
        rf"\newcommand{{\DeletionWinRate}}{{{100 * deletion_summary['fraction_shap_drop_greater_than_random_mean']:.1f}\%}}",
        rf"\newcommand{{\PythonVersion}}{{{metrics['environment']['python_version']}}}",
        rf"\newcommand{{\ShapVersion}}{{{metrics['environment']['shap_version']}}}",
        rf"\newcommand{{\SklearnVersion}}{{{metrics['environment']['scikit_learn_version']}}}",
    ]
    (results_dir / "generated_values.tex").write_text(
        "\n".join(macros) + "\n", encoding="utf-8"
    )

    case_rows: list[str] = []
    for case in cases:
        criterion = case.criterion.replace("%", r"\%")
        outcome = "Sí" if case.correct else "No"
        case_rows.append(
            f"{case.order} & {criterion} & {case.dataset_index} & "
            f"{case.true_class} & {case.predicted_class} & "
            f"{case.confidence:.3f} & {case.margin:.3f} & {outcome} \\\\" 
        )
    (results_dir / "generated_case_rows.tex").write_text(
        "\n".join(case_rows) + "\n\\bottomrule\n", encoding="utf-8"
    )

    deletion_rows: list[str] = []
    for case in cases:
        matching = next(
            row
            for row in metrics["deletion"]["selected_rows"]
            if row["case"] == case.order and row["k"] == 8
        )
        deletion_rows.append(
            f"{case.order} & {matching['original_probability']:.3f} & "
            f"{matching['shap_probability']:.3f} & {matching['shap_drop']:.3f} & "
            f"{matching['random_probability_mean']:.3f} & "
            f"{matching['random_drop_mean']:.3f} \\\\"
        )
    (results_dir / "generated_deletion_rows.tex").write_text(
        "\n".join(deletion_rows) + "\n\\bottomrule\n", encoding="utf-8"
    )


def run_experiment(project_root: Path | None = None) -> dict[str, Any]:
    start = time.perf_counter()
    root = (project_root or _project_root()).resolve()
    figures_dir = root / "figures"
    results_dir = root / "results"
    figures_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    _configure_style()

    digits = load_digits()
    X = digits.data.astype(float, copy=True)
    y = digits.target.astype(int, copy=True)
    dataset_indices = np.arange(len(y))

    train_indices, test_indices = train_test_split(
        dataset_indices,
        test_size=TEST_SIZE,
        random_state=SEED,
        stratify=y,
    )
    X_train, X_test = X[train_indices], X[test_indices]
    y_train, y_test = y[train_indices], y[test_indices]

    model = RandomForestClassifier(
        n_estimators=N_TREES,
        max_features="sqrt",
        random_state=SEED,
        n_jobs=1,
    )
    model.fit(X_train, y_train)
    probabilities = model.predict_proba(X_test)
    predictions = model.classes_[np.argmax(probabilities, axis=1)].astype(int)
    matrix = confusion_matrix(y_test, predictions, labels=model.classes_)
    accuracy = float(accuracy_score(y_test, predictions))
    macro_f1 = float(f1_score(y_test, predictions, average="macro"))

    if not np.all(np.isfinite(probabilities)):
        raise AssertionError("El modelo produjo probabilidades no finitas.")
    if not np.allclose(np.sum(probabilities, axis=1), 1.0, atol=1e-12):
        raise AssertionError("Las probabilidades no suman uno.")
    if set(train_indices).intersection(test_indices):
        raise AssertionError("Hay fuga entre entrenamiento y prueba.")

    cases = _select_cases(y_test, predictions, probabilities, test_indices)
    selected_positions = np.array([case.test_position for case in cases], dtype=int)
    X_selected = X_test[selected_positions]

    background = _stratified_background(
        X_train, y_train, per_class=BACKGROUND_PER_CLASS, seed=SEED
    )
    eligible_random_features = np.flatnonzero(np.var(background, axis=0) > 0)
    explainer = shap.TreeExplainer(
        model,
        data=background,
        feature_perturbation="interventional",
        model_output="probability",
    )
    selected_shap = _explain(explainer, X_selected, len(model.classes_))
    expected_value = np.asarray(explainer.expected_value, dtype=float).reshape(-1)
    if expected_value.shape != (len(model.classes_),):
        raise AssertionError(f"Base SHAP inesperada: {expected_value.shape}")
    reconstructed = expected_value[None, :] + np.sum(selected_shap, axis=1)
    selected_probability = probabilities[selected_positions]
    selected_additivity_error = float(
        np.max(np.abs(reconstructed - selected_probability))
    )
    if selected_additivity_error >= 1e-5:
        raise AssertionError(
            "La comprobación de aditividad local falló: "
            f"error={selected_additivity_error:.3e}."
        )

    replacement = np.mean(background, axis=0)
    selected_deletion_rows = _selected_deletion_test(
        model,
        X_selected,
        cases,
        selected_shap,
        replacement,
        eligible_random_features,
        seed=SEED + 10,
    )

    correct_positions = np.flatnonzero(predictions == y_test)
    X_correct = X_test[correct_positions]
    correct_predictions = predictions[correct_positions]
    correct_probabilities = probabilities[correct_positions]
    correct_shap = _explain(explainer, X_correct, len(model.classes_))
    correct_reconstructed = expected_value[None, :] + np.sum(correct_shap, axis=1)
    correct_additivity_error = float(
        np.max(np.abs(correct_reconstructed - correct_probabilities))
    )
    max_additivity_error = max(selected_additivity_error, correct_additivity_error)
    if max_additivity_error >= 1e-5:
        raise AssertionError(
            "La comprobación de aditividad global falló: "
            f"error={max_additivity_error:.3e}."
        )
    global_rows, global_summary = _global_deletion_test(
        model,
        X_correct,
        correct_predictions,
        correct_probabilities,
        correct_shap,
        replacement,
        eligible_random_features,
        seed=SEED + 20,
    )

    _plot_dataset_examples(digits.images, y, figures_dir)
    _plot_confusion_matrix(matrix, figures_dir)
    _plot_shap_explanations(
        X_selected, cases, selected_shap, probabilities, figures_dir
    )
    _plot_selected_deletion(selected_deletion_rows, cases, figures_dir)
    _plot_global_deletion(global_rows, global_summary, figures_dir)
    _export_selected_images(X_selected, cases, figures_dir)

    runtime = time.perf_counter() - start
    metrics: dict[str, Any] = {
        "schema_version": 1,
        "experiment": {
            "name": "TreeSHAP en clasificación de dígitos manuscritos",
            "random_seed": SEED,
        },
        "dataset": {
            "name": "scikit-learn digits",
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "image_shape": [8, 8],
            "n_classes": int(len(np.unique(y))),
            "pixel_range": [float(X.min()), float(X.max())],
        },
        "split": {
            "test_fraction": TEST_SIZE,
            "stratified": True,
            "n_train": int(len(train_indices)),
            "n_test": int(len(test_indices)),
            "train_test_overlap": 0,
        },
        "model": {
            "type": "RandomForestClassifier",
            "n_estimators": N_TREES,
            "max_features": "sqrt",
            "random_state": SEED,
            "n_jobs": 1,
        },
        "performance": {
            "accuracy": accuracy,
            "macro_f1": macro_f1,
            "n_correct": int(np.sum(predictions == y_test)),
            "n_incorrect": int(np.sum(predictions != y_test)),
            "confusion_matrix": matrix,
        },
        "shap": {
            "explainer": "TreeExplainer",
            "feature_perturbation": "interventional",
            "model_output": "probability",
            "background_sampling": "10 training images per class",
            "background_size": int(background.shape[0]),
            "output_shape_selected": list(selected_shap.shape),
            "expected_value": expected_value,
            "max_additivity_error_selected": selected_additivity_error,
            "max_additivity_error_all_correct": correct_additivity_error,
            "max_additivity_error": max_additivity_error,
        },
        "selected_cases": [asdict(case) for case in cases],
        "deletion": {
            "replacement": "per-feature mean of the stratified SHAP background",
            "random_candidate_rule": "pixels with non-zero variance in the SHAP background",
            "random_candidate_features": eligible_random_features,
            "selected_random_repeats": RANDOM_REPEATS_SELECTED,
            "selected_rows": selected_deletion_rows,
            "global_summary": global_summary,
        },
        "environment": {
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
            "scikit_learn_version": sklearn.__version__,
            "shap_version": shap.__version__,
            "matplotlib_version": matplotlib.__version__,
        },
    }

    _write_json(results_dir / "metrics.json", metrics)
    _write_json(
        results_dir / "execution_metadata.json",
        {
            "runtime_seconds": float(runtime),
            "python_implementation": platform.python_implementation(),
            "operating_system": platform.platform(),
            "python_executable": sys.executable,
        },
    )
    _write_csv(
        results_dir / "selected_cases.csv",
        [asdict(case) for case in cases],
        list(asdict(cases[0]).keys()),
    )
    _write_csv(
        results_dir / "deletion_selected.csv",
        selected_deletion_rows,
        list(selected_deletion_rows[0].keys()),
    )
    _write_csv(
        results_dir / "deletion_global.csv",
        global_rows,
        list(global_rows[0].keys()),
    )
    _write_json(results_dir / "test_indices.json", {"test_indices": test_indices})
    np.savez_compressed(
        results_dir / "shap_values.npz",
        selected_values=selected_shap,
        selected_test_positions=selected_positions,
        correct_values=correct_shap,
        correct_test_positions=correct_positions,
        expected_value=expected_value,
        background=background,
        eligible_random_features=eligible_random_features,
    )
    joblib.dump(model, results_dir / "random_forest_digits.joblib", compress=3)
    _write_latex_results(results_dir, metrics, cases, global_summary)

    print(
        f"OK | accuracy={accuracy:.4f} | macro-F1={macro_f1:.4f} | "
        f"additivity_error={max_additivity_error:.3e} | runtime={runtime:.1f}s"
    )
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Raíz de salida; por defecto, el directorio padre de src/.",
    )
    args = parser.parse_args()
    run_experiment(args.project_root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
