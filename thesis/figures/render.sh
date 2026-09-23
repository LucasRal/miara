#!/usr/bin/env bash
# Regenere TOUTES les figures de la partie 2 du memoire.
#
#   ./thesis/figures/render.sh            # tout
#   ./thesis/figures/render.sh schema-rh  # une figure (nom du .mmd, sans suffixe)
#
# Deux familles de sources :
#   src/*.mmd   diagrammes ecrits a la main (Mermaid), versionnes ;
#   gen/*.py    diagrammes DERIVES du code (metadonnees SQLAlchemy, graphe
#               d'imports, config des alias, dossier prompts/, objets Tool).
# Les .mmd produits par gen/ atterrissent dans src/ : ils sont donc relisibles
# et diffables comme les autres, mais ne doivent jamais etre edites a la main.
#
# Sortie : thesis/figures/out/<nom>.pdf (PDF vectoriel, inclus par Pandoc).
#
# Prerequis, installes une fois par `npm install` dans thesis/figures/ :
#   @mermaid-js/mermaid-cli. Le navigateur est celui deja present sur la
#   machine (cache Playwright) : ce script NE telecharge aucun navigateur.
set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RACINE="$(cd "$ICI/../.." && pwd)"
MMDC="$ICI/node_modules/.bin/mmdc"

[[ -x "$MMDC" ]] || {
  echo "mermaid-cli absent : lancer 'npm install' dans thesis/figures/" >&2
  exit 1
}

# Navigateur : variable d'environnement, sinon le Chromium du cache Playwright.
if [[ -z "${PUPPETEER_EXECUTABLE_PATH:-}" ]]; then
  PUPPETEER_EXECUTABLE_PATH="$(find "${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}" \
      -maxdepth 3 -type f -name chrome 2>/dev/null | sort | tail -1 || true)"
fi
[[ -n "${PUPPETEER_EXECUTABLE_PATH:-}" && -x "$PUPPETEER_EXECUTABLE_PATH" ]] || {
  echo "Aucun navigateur Chromium trouve. Renseigner PUPPETEER_EXECUTABLE_PATH." >&2
  exit 1
}
export PUPPETEER_EXECUTABLE_PATH

mkdir -p "$ICI/out"
# --no-sandbox : le navigateur tourne sous un compte non privilegie sans
# namespaces utilisateur ; aucune page distante n'est chargee.
cat > "$ICI/out/.puppeteer.json" <<'JSON'
{ "args": ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"] }
JSON

# --- 1. Diagrammes derives du code --------------------------------------
if [[ $# -eq 0 ]]; then
  echo "-> generation des diagrammes derives du code"
  ( cd "$RACINE/backend"
    uv run python ../thesis/figures/gen/schema_bdd.py socle  > "$ICI/src/schema-socle.mmd"
    uv run python ../thesis/figures/gen/schema_bdd.py agents > "$ICI/src/schema-agents.mmd"
    uv run python ../thesis/figures/gen/schema_bdd.py exploitation > "$ICI/src/schema-exploitation.mmd"
    uv run python ../thesis/figures/gen/schema_bdd.py rh     > "$ICI/src/schema-rh.mmd"
    uv run python ../thesis/figures/gen/alias_modeles.py     > "$ICI/src/alias-modeles.mmd"
    uv run python ../thesis/figures/gen/catalogue_outils.py  > "$ICI/src/catalogue-outils.mmd" )
  python3 "$ICI/gen/dependances_modules.py" > "$ICI/src/dependances-modules.mmd"
  python3 "$ICI/gen/versions_prompts.py"    > "$ICI/src/versions-prompts.mmd"
fi

# --- 2. Rendu Mermaid -> PDF --------------------------------------------
if [[ $# -gt 0 ]]; then
  sources=()
  for nom in "$@"; do sources+=("$ICI/src/$nom.mmd"); done
else
  mapfile -t sources < <(find "$ICI/src" -maxdepth 1 -name '*.mmd' | sort)
fi

echecs=()
for source in "${sources[@]}"; do
  nom="$(basename "$source" .mmd)"
  echo "-> $nom"
  if ! "$MMDC" --quiet \
      -i "$source" \
      -o "$ICI/out/$nom.pdf" \
      -p "$ICI/out/.puppeteer.json" \
      -c "$ICI/mermaid.json" \
      -b transparent \
      --pdfFit; then
    echecs+=("$nom")
  fi
done

if [[ ${#echecs[@]} -gt 0 ]]; then
  echo "ECHEC de rendu : ${echecs[*]}" >&2
  exit 1
fi
echo "Figures ecrites dans thesis/figures/out/"
