param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$TaskProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $TaskProjectRoot

$TaskVenvPython = Join-Path $TaskProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $TaskVenvPython)) {
    if ($SkipInstall) {
        throw "No existe .venv. Ejecute reproduce.ps1 sin -SkipInstall la primera vez."
    }
    $TaskPyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($TaskPyLauncher) {
        & py -3.11 -m venv .venv
    }
    else {
        & python -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno virtual." }
}

& $TaskVenvPython -c "import struct, sys; assert sys.version_info[:2] == (3, 11) and struct.calcsize('P') * 8 == 64, 'Se requiere Python 3.11 de 64 bits.'"
if ($LASTEXITCODE -ne 0) { throw "El entorno no usa Python 3.11 de 64 bits." }

if (-not $SkipInstall) {
    & $TaskVenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "No se pudo actualizar pip." }
    & $TaskVenvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "No se pudieron instalar las dependencias." }
}

& $TaskVenvPython -m pip check
if ($LASTEXITCODE -ne 0) { throw "El entorno contiene dependencias incompatibles." }

& $TaskVenvPython -m ipykernel install --sys-prefix --name shap-repro --display-name "Python (SHAP reproducible)"
if ($LASTEXITCODE -ne 0) { throw "No se pudo registrar el kernel local." }

& $TaskVenvPython -m nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=shap-repro --ExecutePreprocessor.timeout=900 notebooks\shap_digits.ipynb
if ($LASTEXITCODE -ne 0) { throw "La ejecución del notebook falló." }

$TaskTinyLatexmk = Join-Path $env:APPDATA "TinyTeX\bin\windows\latexmk.exe"
if (Test-Path -LiteralPath $TaskTinyLatexmk) {
    $TaskLatexBin = Split-Path -Parent $TaskTinyLatexmk
    $TaskOriginalPath = $env:PATH
    try {
        $env:PATH = "$TaskLatexBin;$TaskOriginalPath"
        & $TaskTinyLatexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex
        $TaskLatexExitCode = $LASTEXITCODE
    }
    finally {
        $env:PATH = $TaskOriginalPath
    }
    if ($TaskLatexExitCode -ne 0) { throw "La compilación de paper.tex falló." }
}
else {
    $TaskPdfLatex = Get-Command pdflatex -ErrorAction SilentlyContinue
    $TaskBibtex = Get-Command bibtex -ErrorAction SilentlyContinue
    if (-not $TaskPdfLatex -or -not $TaskBibtex) {
        throw "No se encontraron pdflatex y bibtex. Instale TinyTeX, TeX Live o MiKTeX."
    }
    & $TaskPdfLatex.Source -interaction=nonstopmode -halt-on-error paper.tex
    if ($LASTEXITCODE -ne 0) { throw "La primera pasada de pdflatex falló." }
    & $TaskBibtex.Source paper
    if ($LASTEXITCODE -ne 0) { throw "La compilación de la bibliografía falló." }
    & $TaskPdfLatex.Source -interaction=nonstopmode -halt-on-error paper.tex
    if ($LASTEXITCODE -ne 0) { throw "La segunda pasada de pdflatex falló." }
    & $TaskPdfLatex.Source -interaction=nonstopmode -halt-on-error paper.tex
    if ($LASTEXITCODE -ne 0) { throw "La tercera pasada de pdflatex falló." }
}

& $TaskVenvPython src\validate_outputs.py
if ($LASTEXITCODE -ne 0) { throw "La validación final falló." }

Write-Host "Paquete reproducido y validado correctamente." -ForegroundColor Green
