#!/usr/bin/env bash
# Compile une partie du mémoire en PDF avec Pandoc.
#
#   ./thesis/build.sh            # partie1 (défaut)
#   ./thesis/build.sh partie1 partie2
#
# Sortie : thesis/build/<partie>.pdf
# Prérequis : pandoc >= 3, un moteur XeLaTeX (paquets Debian/Ubuntu :
#   pandoc texlive-xetex texlive-lang-french texlive-latex-recommended
#   texlive-fonts-recommended lmodern)
set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARTIES=("${@:-partie1}")

command -v pandoc >/dev/null || { echo "pandoc absent : voir thesis/README.md" >&2; exit 1; }

MOTEUR="${THESIS_PDF_ENGINE:-xelatex}"
if ! command -v "$MOTEUR" >/dev/null; then
  echo "Moteur PDF '$MOTEUR' absent : voir thesis/README.md" >&2
  exit 1
fi

mkdir -p "$ICI/build"

for partie in "${PARTIES[@]}"; do
  dossier="$ICI/$partie"
  [[ -d "$dossier" ]] || { echo "Partie inconnue : $partie" >&2; exit 1; }

  # Ordre de compilation = ordre lexicographique des fichiers (00-, 01-, ...).
  mapfile -t chapitres < <(find "$dossier" -maxdepth 1 -name '*.md' | sort)
  [[ ${#chapitres[@]} -gt 0 ]] || { echo "Aucun chapitre dans $dossier" >&2; exit 1; }

  # Métadonnées propres à la partie (sous-titre, etc.), si le fichier existe.
  meta_partie=()
  [[ -f "$dossier/partie.yaml" ]] && meta_partie=(--metadata-file="$dossier/partie.yaml")

  echo "-> $partie : ${#chapitres[@]} fichier(s)"
  pandoc \
    --metadata-file="$ICI/pandoc/metadata.yaml" \
    "${meta_partie[@]}" \
    --resource-path="$ICI:$dossier" \
    --include-in-header="$ICI/pandoc/entete.tex" \
    --citeproc \
    --bibliography="$ICI/refs.bib" \
    --csl="$ICI/pandoc/iso690-author-date-fr.csl" \
    --pdf-engine="$MOTEUR" \
    --top-level-division=chapter \
    --number-sections \
    --toc --toc-depth=2 \
    -o "$ICI/build/$partie.pdf" \
    "${chapitres[@]}"
  echo "   ecrit : thesis/build/$partie.pdf"
done
