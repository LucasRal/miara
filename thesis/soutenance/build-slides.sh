#!/usr/bin/env bash
# Compile les diapositives de soutenance en PDF (Beamer).
#
#   ./thesis/soutenance/build-slides.sh
#
# Sortie : thesis/build/diapositives.pdf
# Mêmes prérequis que thesis/build.sh (pandoc + XeLaTeX).
set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THESIS="$(cd "$ICI/.." && pwd)"

command -v pandoc >/dev/null || { echo "pandoc absent : voir thesis/README.md" >&2; exit 1; }
MOTEUR="${THESIS_PDF_ENGINE:-xelatex}"
command -v "$MOTEUR" >/dev/null || { echo "Moteur PDF '$MOTEUR' absent" >&2; exit 1; }

mkdir -p "$THESIS/build"
pandoc \
  --to=beamer \
  --resource-path="$THESIS:$ICI" \
  --pdf-engine="$MOTEUR" \
  --slide-level=1 \
  -o "$THESIS/build/diapositives.pdf" \
  "$ICI/diapositives.md"
echo "   ecrit : thesis/build/diapositives.pdf"
