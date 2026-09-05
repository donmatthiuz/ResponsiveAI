"""Valida integridad, coherencia y actualidad del paquete entregable."""

from __future__ import annotations

import csv
import json
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any

import joblib
import nbformat
import numpy as np
from sklearn.datasets import load_digits
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    "paper.tex",
    "paper.pdf",
    "paper.log",
    "references.bib",
    "README.md",
    "requirements.txt",
    "reproduce.ps1",
    "build_submission.ps1",
    "src/run_experiment.py",
    "src/validate_outputs.py",
    "notebooks/shap_digits.ipynb",
    "prompts/prompt_log.md",
    "LIMITATIONS.md",
    "results/metrics.json",
    "results/execution_metadata.json",
    "results/selected_cases.csv",
    "results/deletion_selected.csv",
    "results/deletion_global.csv",
    "results/generated_values.tex",
    "results/generated_case_rows.tex",
    "results/generated_deletion_rows.tex",
    "results/random_forest_digits.joblib",
    "results/test_indices.json",
    "results/shap_values.npz",
]
for stem in (
    "dataset_examples",
    "confusion_matrix",
    "shap_explanations",
    "deletion_selected",
    "deletion_global",
):
    REQUIRED_FILES.extend([f"figures/{stem}.png", f"figures/{stem}.pdf"])
for case_number in (1, 2, 3):
    REQUIRED_FILES.append(f"figures/test_image_{case_number}.png")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _close(left: float, right: float, tolerance: float = 1e-12) -> None:
    if not np.isclose(left, right, rtol=0.0, atol=tolerance):
        raise AssertionError(f"Valores distintos: {left!r} != {right!r}")


def _validate_pinned_environment() -> None:
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    for line in lines:
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        if "==" not in clean:
            raise AssertionError(f"Dependencia sin versión exacta: {clean}")
        package, expected = clean.split("==", maxsplit=1)
        installed = version(package)
        if installed != expected:
            raise AssertionError(
                f"Versión distinta para {package}: instalada={installed}, esperada={expected}"
            )


def _validate_binary_assets() -> None:
    for relative in REQUIRED_FILES:
        path = ROOT / relative
        if path.suffix.lower() == ".png":
            payload = path.read_bytes()
            assert payload.startswith(b"\x89PNG\r\n\x1a\n") and len(payload) > 500
        elif path.suffix.lower() == ".pdf":
            payload = path.read_bytes()
            assert payload.startswith(b"%PDF-") and len(payload) > 5_000


def _validate_notebook() -> None:
    path = ROOT / "notebooks/shap_digits.ipynb"
    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)
    code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
    assert code_cells and all(cell.execution_count is not None for cell in code_cells)
    source = "\n".join(cell.source for cell in code_cells)
    assert "from run_experiment import run_experiment" in source
    assert "run_experiment(ROOT)" in source
    text_outputs: list[str] = []
    for cell in code_cells:
        for output in cell.get("outputs", []):
            if output.get("output_type") == "stream":
                text_outputs.append(output.get("text", ""))
    if "OK | accuracy=" not in "".join(text_outputs):
        raise AssertionError("El notebook no contiene evidencia de ejecución completa.")


def _validate_latex(metrics: dict[str, Any]) -> None:
    pdf_path = ROOT / "paper.pdf"
    dependencies = [
        ROOT / "paper.tex",
        ROOT / "references.bib",
        *(ROOT / "figures").glob("*.pdf"),
        *(ROOT / "results").glob("generated_*.tex"),
    ]
    newest_input = max(path.stat().st_mtime_ns for path in dependencies)
    if pdf_path.stat().st_mtime_ns < newest_input:
        raise AssertionError("paper.pdf es anterior a uno de sus insumos.")

    log = (ROOT / "paper.log").read_text(encoding="utf-8", errors="ignore")
    forbidden = [
        "Citation `",
        "Reference `",
        "There were undefined references",
        "Fatal error occurred",
        "! LaTeX Error:",
    ]
    found = [fragment for fragment in forbidden if fragment in log]
    if found:
        raise AssertionError(f"El log de LaTeX contiene errores: {found}")

    generated = (ROOT / "results/generated_values.tex").read_text(encoding="utf-8")
    accuracy = metrics["performance"]["accuracy"]
    expected_fragments = [
        rf"\newcommand{{\TestAccuracy}}{{{100 * accuracy:.2f}\%}}",
        rf"\newcommand{{\MacroFOne}}{{{metrics['performance']['macro_f1']:.3f}}}",
        rf"\newcommand{{\CorrectTestCases}}{{{metrics['performance']['n_correct']}}}",
        rf"\newcommand{{\RandomCandidateFeatures}}{{{metrics['deletion']['global_summary']['random_candidate_features']}}}",
    ]
    missing = [fragment for fragment in expected_fragments if fragment not in generated]
    if missing:
        raise AssertionError(f"Macros LaTeX obsoletas o ausentes: {missing}")

    case_rows = (ROOT / "results/generated_case_rows.tex").read_text(encoding="utf-8")
    deletion_rows = (ROOT / "results/generated_deletion_rows.tex").read_text(
        encoding="utf-8"
    )
    assert case_rows.count(r"\\") == 3 and r"\bottomrule" in case_rows
    assert deletion_rows.count(r"\\") == 3 and r"\bottomrule" in deletion_rows


def main() -> int:
    missing = [relative for relative in REQUIRED_FILES if not (ROOT / relative).is_file()]
    if missing:
        raise AssertionError("Faltan archivos:\n- " + "\n- ".join(missing))

    _validate_pinned_environment()
    _validate_binary_assets()

    metrics = json.loads((ROOT / "results/metrics.json").read_text(encoding="utf-8"))
    execution = json.loads(
        (ROOT / "results/execution_metadata.json").read_text(encoding="utf-8")
    )
    assert metrics["schema_version"] == 1
    assert "runtime_seconds" not in metrics["experiment"]
    assert float(execution["runtime_seconds"]) > 0
    assert execution["python_implementation"]
    assert execution["operating_system"]
    assert execution["python_executable"]
    assert metrics["performance"]["accuracy"] >= 0.94
    assert (
        metrics["performance"]["n_correct"]
        + metrics["performance"]["n_incorrect"]
        == metrics["split"]["n_test"]
    )
    assert metrics["shap"]["output_shape_selected"] == [3, 64, 10]
    assert metrics["shap"]["max_additivity_error"] < 1e-5
    assert len(metrics["selected_cases"]) == 3

    digits = load_digits()
    indices = np.arange(len(digits.target))
    seed = int(metrics["experiment"]["random_seed"])
    train_indices, test_indices = train_test_split(
        indices,
        test_size=float(metrics["split"]["test_fraction"]),
        random_state=seed,
        stratify=digits.target,
    )
    saved_indices = np.asarray(
        json.loads((ROOT / "results/test_indices.json").read_text(encoding="utf-8"))[
            "test_indices"
        ],
        dtype=int,
    )
    assert np.array_equal(saved_indices, test_indices)
    assert len(np.intersect1d(train_indices, test_indices)) == 0
    assert metrics["split"]["n_train"] == len(train_indices)
    assert metrics["split"]["n_test"] == len(test_indices)

    X_test = digits.data[test_indices]
    y_test = digits.target[test_indices]
    model = joblib.load(ROOT / "results/random_forest_digits.joblib")
    probabilities = model.predict_proba(X_test)
    predictions = model.classes_[np.argmax(probabilities, axis=1)]
    _close(float(accuracy_score(y_test, predictions)), metrics["performance"]["accuracy"])
    _close(
        float(f1_score(y_test, predictions, average="macro")),
        metrics["performance"]["macro_f1"],
    )
    matrix = confusion_matrix(y_test, predictions, labels=model.classes_)
    assert np.array_equal(matrix, np.asarray(metrics["performance"]["confusion_matrix"]))

    selected_csv = _read_csv(ROOT / "results/selected_cases.csv")
    assert len(selected_csv) == len(metrics["selected_cases"]) == 3
    for csv_row, json_row in zip(selected_csv, metrics["selected_cases"]):
        for key in (
            "order",
            "test_position",
            "dataset_index",
            "true_class",
            "predicted_class",
            "comparison_class",
        ):
            assert int(csv_row[key]) == int(json_row[key])
        assert csv_row["criterion"] == json_row["criterion"]
        _close(float(csv_row["confidence"]), float(json_row["confidence"]))
        _close(float(csv_row["margin"]), float(json_row["margin"]))

    archive = np.load(ROOT / "results/shap_values.npz")
    selected_values = archive["selected_values"]
    correct_values = archive["correct_values"]
    expected_value = archive["expected_value"]
    selected_positions = archive["selected_test_positions"].astype(int)
    correct_positions = archive["correct_test_positions"].astype(int)
    assert selected_values.shape == (3, 64, 10)
    assert correct_values.shape == (metrics["performance"]["n_correct"], 64, 10)
    assert np.array_equal(
        selected_positions,
        np.asarray([row["test_position"] for row in metrics["selected_cases"]]),
    )
    assert np.array_equal(correct_positions, np.flatnonzero(predictions == y_test))

    selected_reconstruction = expected_value + np.sum(selected_values, axis=1)
    selected_error = float(
        np.max(np.abs(selected_reconstruction - probabilities[selected_positions]))
    )
    correct_reconstruction = expected_value + np.sum(correct_values, axis=1)
    correct_error = float(
        np.max(np.abs(correct_reconstruction - probabilities[correct_positions]))
    )
    _close(selected_error, metrics["shap"]["max_additivity_error_selected"], 1e-12)
    _close(correct_error, metrics["shap"]["max_additivity_error_all_correct"], 1e-12)
    _close(
        max(selected_error, correct_error),
        metrics["shap"]["max_additivity_error"],
        1e-12,
    )

    eligible = archive["eligible_random_features"].astype(int)
    assert np.array_equal(
        eligible, np.flatnonzero(np.var(archive["background"], axis=0) > 0)
    )
    assert np.array_equal(
        eligible, np.asarray(metrics["deletion"]["random_candidate_features"])
    )
    assert (
        len(eligible)
        == metrics["deletion"]["global_summary"]["random_candidate_features"]
    )
    selected_classes = np.asarray(
        [row["predicted_class"] for row in metrics["selected_cases"]], dtype=int
    )
    selected_for_class = selected_values[np.arange(3), :, selected_classes]
    selected_top8 = np.argsort(-selected_for_class, axis=1)[:, :8]
    assert np.all(np.take_along_axis(selected_for_class, selected_top8, axis=1) > 0)
    assert np.all(np.isin(selected_top8, eligible))

    correct_classes = predictions[correct_positions]
    correct_for_class = correct_values[
        np.arange(len(correct_positions)), :, correct_classes
    ]
    positive_counts = np.sum(correct_for_class > 0, axis=1)
    correct_top8 = np.argsort(-correct_for_class, axis=1)[:, :8]
    assert int(np.min(positive_counts)) == int(
        metrics["deletion"]["global_summary"][
            "minimum_positive_attributions_per_case"
        ]
    )
    assert np.all(np.isin(correct_top8, eligible))

    selected_deletion_csv = _read_csv(ROOT / "results/deletion_selected.csv")
    selected_deletion_json = metrics["deletion"]["selected_rows"]
    assert len(selected_deletion_csv) == len(selected_deletion_json) == 15
    for csv_row, json_row in zip(selected_deletion_csv, selected_deletion_json):
        assert int(csv_row["case"]) == int(json_row["case"])
        assert int(csv_row["k"]) == int(json_row["k"])
        for key in (
            "original_probability",
            "shap_probability",
            "shap_drop",
            "random_probability_mean",
            "random_drop_mean",
        ):
            _close(float(csv_row[key]), float(json_row[key]))

    global_rows = _read_csv(ROOT / "results/deletion_global.csv")
    summary = metrics["deletion"]["global_summary"]
    assert (
        len(global_rows)
        == summary["n_correct_cases"]
        == metrics["performance"]["n_correct"]
    )
    shap_drops = np.asarray([float(row["shap_drop_at_8"]) for row in global_rows])
    random_drops = np.asarray(
        [float(row["random_mean_drop_at_8"]) for row in global_rows]
    )
    _close(float(np.median(shap_drops)), summary["median_shap_drop"])
    _close(float(np.median(random_drops)), summary["median_random_mean_drop"])
    _close(
        float(np.median(shap_drops - random_drops)),
        summary["median_paired_difference"],
    )

    _validate_notebook()
    _validate_latex(metrics)

    paper_source = (ROOT / "paper.tex").read_text(encoding="utf-8")
    if "Nombre del estudiante" in paper_source:
        print("ADVERTENCIA: reemplace \\StudentName antes de entregar.")
    print(
        "VALIDACIÓN OK | "
        f"accuracy={metrics['performance']['accuracy']:.4f} | "
        f"drop@8 SHAP={summary['median_shap_drop']:.3f} | "
        f"drop@8 azar={summary['median_random_mean_drop']:.3f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
