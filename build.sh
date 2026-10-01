#!/usr/bin/env bash
# Genera los diagramas Mermaid y compila board.pdf e investigacion.pdf.
# Requiere nix; en otro sistema basta con tener mmdc, tectonic y pandoc en el PATH.
set -euo pipefail
cd "$(dirname "$0")"

run() {
  if command -v mmdc >/dev/null && command -v tectonic >/dev/null && command -v pandoc >/dev/null; then
    bash -c "$1"
  else
    nix-shell -p mermaid-cli tectonic pandoc --run "$1"
  fi
}

run '
for f in diagramas/*.mmd; do
  mmdc -p diagramas/puppeteer.json -i "$f" -o "${f%.mmd}.pdf" --pdfFit -t neutral -b white
done
tectonic -X compile board.tex
pandoc investigacion.md -o investigacion.pdf --pdf-engine=tectonic \
  -V mainfont="TeX Gyre Heros" -V geometry:margin=22mm -V lang=es -V colorlinks=true
'
