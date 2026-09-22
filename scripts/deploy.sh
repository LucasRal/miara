#!/usr/bin/env bash
#
# Déploiement Miara en une commande :
#   git -> uv sync -> alembic upgrade -> npm ci && npm run build -> restart -> /health
#
# Usage (sur le VPS) :
#   sudo -u miara /srv/miara/scripts/deploy.sh                 # dernier commit de la branche
#   sudo -u miara /srv/miara/scripts/deploy.sh --ref <sha>     # déploie une révision précise
#   sudo -u miara /srv/miara/scripts/deploy.sh --skip-build    # relance sans reconstruire le front
#
# RETOUR ARRIÈRE : le SHA déployé précédemment est affiché au début et à la fin.
#   sudo -u miara /srv/miara/scripts/deploy.sh --ref <ancien-sha>
# C'est volontairement le même chemin de code que le déploiement normal :
# un retour arrière qui emprunte un chemin jamais testé n'est pas un filet.
# -E : le piège ERR doit aussi se déclencher à l'intérieur des fonctions.
set -eEuo pipefail

APP_USER="${APP_USER:-miara}"
APP_DIR="${APP_DIR:-/srv/miara}"
ENV_FILE="${ENV_FILE:-/etc/miara/.env}"
LOG_FILE="${LOG_FILE:-/var/log/miara/deploy.log}"
API_HEALTH_URL="${API_HEALTH_URL:-http://127.0.0.1:8010/health}"
WEB_URL="${WEB_URL:-http://127.0.0.1:3010/}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-90}"
UNITS=(miara-api miara-worker-heavy miara-worker-light miara-web)

REF=""
SKIP_BUILD=0

log()  { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
info() { printf '   %s\n' "$*"; }
die()  { printf '\033[31mERREUR: %s\033[0m\n' "$*" >&2; exit 1; }

usage() {
  sed -n '3,14p' "$0"
  exit "${1:-0}"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --ref)        REF="${2:-}"; [[ -n "$REF" ]] || die "--ref attend une révision"; shift 2 ;;
      --skip-build) SKIP_BUILD=1; shift ;;
      -h|--help)    usage 0 ;;
      *)            die "argument inconnu : $1 (voir --help)" ;;
    esac
  done
}

ensure_identity() {
  # Le déploiement doit tourner sous l'identité qui possède les fichiers, sinon
  # le prochain démarrage échoue sur un .venv ou un .next appartenant à root.
  if [[ $EUID -eq 0 ]]; then
    info "relancé sous l'utilisateur ${APP_USER}"
    exec sudo -u "$APP_USER" -H "$0" "$@"
  fi
  [[ "$(id -un)" == "$APP_USER" ]] \
    || die "à lancer en ${APP_USER} (sudo -u ${APP_USER} $0)"
}

load_env() {
  [[ -r "$ENV_FILE" ]] || die "${ENV_FILE} illisible (droits 640 root:${APP_USER} ?)"
  # `set -a` : tout ce qui est défini ici part dans l'environnement des
  # sous-processus (alembic a besoin de DATABASE_URL_ADMIN, `next build` des
  # NEXT_PUBLIC_*, qui sont figées à la compilation et non au démarrage).
  set -a
  # shellcheck disable=SC1090  # chemin connu à l'exécution seulement
  source "$ENV_FILE"
  set +a
  : "${DATABASE_URL_ADMIN:?absent de ${ENV_FILE}}"
  : "${DATABASE_URL:?absent de ${ENV_FILE}}"
}

record_current_sha() {
  PREVIOUS_SHA="$(git -C "$APP_DIR" rev-parse HEAD)"
  info "révision actuelle : ${PREVIOUS_SHA}"
}

update_sources() {
  log "Sources"
  git -C "$APP_DIR" fetch --prune --tags origin
  if [[ -n "$REF" ]]; then
    # Détaché volontairement : un retour arrière ne doit pas déplacer la
    # branche, pour que le prochain déploiement normal reparte du bon endroit.
    git -C "$APP_DIR" checkout --detach "$REF"
  else
    local branch
    branch="$(git -C "$APP_DIR" rev-parse --abbrev-ref HEAD)"
    [[ "$branch" != "HEAD" ]] \
      || die "HEAD est détaché : préciser --ref, ou se replacer sur une branche."
    git -C "$APP_DIR" pull --ff-only origin "$branch"
  fi
  TARGET_SHA="$(git -C "$APP_DIR" rev-parse HEAD)"
  info "révision déployée : ${TARGET_SHA}"
  # Un dépôt sali à la main sur le serveur fait échouer le prochain pull et
  # rend le retour arrière imprévisible : on le signale, sans bloquer.
  if [[ -n "$(git -C "$APP_DIR" status --porcelain)" ]]; then
    info "ATTENTION : modifications locales non versionnées présentes"
  fi
}

sync_backend() {
  log "Backend (uv)"
  # --frozen : on installe EXACTEMENT uv.lock. Une résolution opportuniste sur
  # le serveur produirait un environnement différent de celui testé.
  (cd "${APP_DIR}/backend" && uv sync --frozen --no-dev)
}

run_migrations() {
  log "Migrations (alembic)"
  # Les migrations passent par miara_admin (BYPASSRLS) ; le runtime reste sur
  # miara_app (ADR-002). alembic/env.py lit DATABASE_URL_ADMIN, pas DATABASE_URL.
  (cd "${APP_DIR}/backend" && uv run --frozen alembic upgrade head)
}

build_frontend() {
  if [[ $SKIP_BUILD -eq 1 ]]; then
    info "build frontend ignoré (--skip-build)"
    return
  fi
  log "Frontend (npm)"
  # `npm ci` et non `npm install` : install peut réécrire package-lock.json et
  # faire diverger le serveur du dépôt.
  (cd "${APP_DIR}/frontend" && npm ci --no-audit --no-fund && npm run build)
}

restart_services() {
  log "Redémarrage des services"
  # Un seul appel systemctl : les quatre services repartent ensemble, ce qui
  # évite qu'un front neuf parle à une API encore ancienne.
  sudo systemctl restart "${UNITS[@]}"
  local unit
  for unit in "${UNITS[@]}"; do
    info "${unit} : $(systemctl is-active "$unit" 2>/dev/null || true)"
  done
}

wait_for_health() {
  log "Vérification /health"
  local deadline=$((SECONDS + HEALTH_TIMEOUT))
  local body=""
  while (( SECONDS < deadline )); do
    # /health agrège BDD + RabbitMQ + Redis et répond 503 si l'un tombe :
    # c'est la seule vérification qui prouve que le déploiement est utilisable.
    if body="$(curl -fsS --max-time 5 "$API_HEALTH_URL" 2>/dev/null)"; then
      info "API : ${body}"
      if curl -fsS -o /dev/null --max-time 10 "$WEB_URL"; then
        info "Frontend : réponse 2xx sur ${WEB_URL}"
        return 0
      fi
      info "frontend pas encore prêt, nouvelle tentative..."
    fi
    sleep 3
  done
  return 1
}

rollback_hint() {
  cat >&2 <<EOS

  Déploiement en échec. Journaux :
    journalctl -u miara-api -u miara-web -u miara-worker-heavy -n 200 --no-pager

  Retour arrière (même chemin de code, donc testé) :
    sudo -u ${APP_USER} ${APP_DIR}/scripts/deploy.sh --ref ${PREVIOUS_SHA:-<voir git reflog>}

  Rappel : une migration Alembic déjà appliquée n'est PAS annulée par ce
  retour arrière. Vérifier si le code précédent tolère le schéma courant,
  sinon lancer "alembic downgrade <révision>" avant de rejouer.
EOS
}

main() {
  parse_args "$@"
  ensure_identity "$@"
  load_env
  # Toute la sortie est archivée : `deploy.log` est la première chose qu'on
  # relit quand une mise en production se passe mal.
  exec > >(tee -a "$LOG_FILE") 2>&1
  log "Déploiement Miara - $(date -Is)"
  # Toute sortie en erreur affiche le même mode d'emploi de retour arrière,
  # quel que soit l'endroit où le déploiement a cassé.
  trap rollback_hint ERR
  record_current_sha
  update_sources
  sync_backend
  run_migrations
  build_frontend
  restart_services
  if wait_for_health; then
    log "Déploiement réussi"
    info "révision déployée : ${TARGET_SHA}"
    info "révision précédente (retour arrière) : ${PREVIOUS_SHA}"
  else
    rollback_hint
    exit 1
  fi
  trap - ERR
}

main "$@"
