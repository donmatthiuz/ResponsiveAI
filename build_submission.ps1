$ErrorActionPreference = "Stop"

$TaskProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $TaskProjectRoot

$TaskPython = Join-Path $TaskProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $TaskPython)) {
    throw "No existe .venv. Ejecute reproduce.ps1 antes de construir la entrega."
}

& $TaskPython src\validate_outputs.py
if ($LASTEXITCODE -ne 0) { throw "La validación falló; no se creó el ZIP." }

$TaskFiles = @(
    ".gitignore",
    "README.md",
    "LIMITATIONS.md",
    "requirements.txt",
    "reproduce.ps1",
    "build_submission.ps1",
    "paper.tex",
    "paper.pdf",
    "paper.log",
    "references.bib",
    "src\run_experiment.py",
    "src\validate_outputs.py",
    "notebooks\shap_digits.ipynb",
    "prompts\prompt_log.md",
    "figures\dataset_examples.png",
    "figures\dataset_examples.pdf",
    "figures\confusion_matrix.png",
    "figures\confusion_matrix.pdf",
    "figures\shap_explanations.png",
    "figures\shap_explanations.pdf",
    "figures\deletion_selected.png",
    "figures\deletion_selected.pdf",
    "figures\deletion_global.png",
    "figures\deletion_global.pdf",
    "figures\test_image_1.png",
    "figures\test_image_2.png",
    "figures\test_image_3.png",
    "results\metrics.json",
    "results\execution_metadata.json",
    "results\selected_cases.csv",
    "results\deletion_selected.csv",
    "results\deletion_global.csv",
    "results\generated_values.tex",
    "results\generated_case_rows.tex",
    "results\generated_deletion_rows.tex",
    "results\random_forest_digits.joblib",
    "results\test_indices.json",
    "results\shap_values.npz"
)

$TaskMissing = @($TaskFiles | Where-Object {
    -not (Test-Path -LiteralPath (Join-Path $TaskProjectRoot $_) -PathType Leaf)
})
if ($TaskMissing.Count -gt 0) {
    throw "Faltan archivos de entrega: $($TaskMissing -join ', ')"
}

$TaskDist = Join-Path $TaskProjectRoot ".dist"
$TaskStage = Join-Path $TaskDist "submission_stage"
$TaskZip = Join-Path $TaskDist "Tarea_1_SHAP_reproducible.zip"
New-Item -ItemType Directory -Path $TaskDist -Force | Out-Null

$TaskDistFull = [IO.Path]::GetFullPath($TaskDist).TrimEnd('\', '/')
$TaskStageFull = [IO.Path]::GetFullPath($TaskStage).TrimEnd('\', '/')
$TaskExpectedPrefix = $TaskDistFull + [IO.Path]::DirectorySeparatorChar
if (-not $TaskStageFull.StartsWith($TaskExpectedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "La carpeta temporal quedó fuera de .dist; se canceló la operación."
}
if ([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($TaskZip)) -ne $TaskDistFull) {
    throw "El ZIP quedó fuera de .dist; se canceló la operación."
}

if (Test-Path -LiteralPath $TaskStage) {
    Remove-Item -LiteralPath $TaskStage -Recurse -Force
}
if (Test-Path -LiteralPath $TaskZip) {
    Remove-Item -LiteralPath $TaskZip -Force
}
New-Item -ItemType Directory -Path $TaskStage | Out-Null

foreach ($TaskRelative in $TaskFiles) {
    $TaskSource = Join-Path $TaskProjectRoot $TaskRelative
    $TaskDestination = Join-Path $TaskStage $TaskRelative
    $TaskDestinationParent = Split-Path -Parent $TaskDestination
    New-Item -ItemType Directory -Path $TaskDestinationParent -Force | Out-Null
    Copy-Item -LiteralPath $TaskSource -Destination $TaskDestination
}

$TaskManifestLines = @(
    Get-ChildItem -LiteralPath $TaskStage -File -Recurse |
        Sort-Object FullName |
        ForEach-Object {
            $TaskRelative = $_.FullName.Substring($TaskStageFull.Length + 1).Replace('\', '/')
            $TaskHash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            "$TaskHash  $TaskRelative"
        }
)
$TaskUtf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllLines(
    (Join-Path $TaskStage "MANIFEST.sha256"),
    [string[]]$TaskManifestLines,
    $TaskUtf8NoBom
)

Compress-Archive -Path (Join-Path $TaskStage "*") -DestinationPath $TaskZip -CompressionLevel Optimal
Remove-Item -LiteralPath $TaskStage -Recurse -Force

Write-Host "Entrega creada: $TaskZip" -ForegroundColor Green
