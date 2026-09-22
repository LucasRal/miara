#!/usr/bin/env bash
#
# Restauration d'une sauvegarde Miara produite par scripts/backup_db.sh.
#
#   sudo /srv/miara/scripts/restore_db.sh --dump <fichier> --into <base>
#
# Options :
#   --dump <fichier>   sauvegarde .dump (format custom). Défaut : la plus récente.
#   --into <base>      base CIBLE. Défaut : miara_restore_test (base jetable).
#   --create           crée la base cible si elle n'existe pas.
#   --drop-existing    supprime puis recrée la base cible (jetable uniquement).
#   --force            autorise explicitement la restauration sur la base de
#                      production. Sans ce drapeau, le script refuse.
#   --dry-run          n'écrit rien : liste seulement le contenu du dump.
#
# Pourquoi cette prudence : une restauration lancée sur la mauvaise base efface
# des données de production en quelques secondes, sans confirmation possible.
# Le défaut du script est donc une base jetable, jamais la production.
#
# La restauration tourne en `postgres` (superutilisateur) : indispensable, car
# les tables portent FORCE ROW LEVEL SECURITY et appartiennent à miara_admin ;
# un rôle applicatif ne pourrait ni recréer les politiques ni écrire dedans.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/miara}"
PROD_DB="${PROD_DB:-miara}"
DUMP=""
TARGET_DB="miara_restore_test"
CREATE=0
DROP_EXISTING=0
FORCE=0
DRY_RUN=0

log() { printf '%s [restore] %s\n' "$(date -Is)" "$*"; }
die() { printf '%s [restore] ERREUR: %s\n' "$(date -Is)" "$*" >&2; exit 1; }

usage() { sed -n '3,20p' "$0"; exit "${1:-0}"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dump)          DUMP="${2:-}"; shift 2 ;;
    --into)          TARGET_DB="${2:-}"; shift 2 ;;
    --create)        CREATE=1; shift ;;
    --drop-existing) DROP_EXISTING=1; shift ;;
    --force)         FORCE=1; shift ;;
    --dry-run)       DRY_RUN=1; shift ;;
    -h|--help)       usage 0 ;;
    *)               die "argument inconnu : $1 (voir --help)" ;;
  esac
done

[[ $EUID -eq 0 ]] || die "à lancer avec sudo."
id -u postgres &>/dev/null || die "utilisateur système postgres introuvable."
[[ -n "$TARGET_DB" ]] || die "--into attend un nom de base."

if [[ -z "$DUMP" ]]; then
  DUMP="$(find "$BACKUP_DIR" -maxdepth 1 -name '*.dump' -type f -printf '%T@ %p\n' \
    | sort -rn | head -1 | cut -d' ' -f2-)"
  [[ -n "$DUMP" ]] || die "aucune sauvegarde trouvée dans ${BACKUP_DIR}."
  log "sauvegarde la plus récente : ${DUMP}"
fi
[[ -f "$DUMP" ]] || die "fichier introuvable : ${DUMP}"

# Le fichier doit être lisible par postgres, qui n'est ni root ni dans son
# groupe, et pg_restore a besoin d'un fichier RÉELLEMENT ouvrable (il se
# repositionne dedans, un descripteur hérité sur stdin ne suffit pas pour une
# restauration complète). On passe donc par une copie temporaire qui appartient
# à postgres en 0600 : le dump contient toute la base, il ne doit à aucun
# moment être lisible par les autres comptes de la machine.
WORK="$(mktemp -d /tmp/miara-restore.XXXXXX)"
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT
install -o postgres -g postgres -m 600 "$DUMP" "${WORK}/dump"
chown postgres:postgres "$WORK"
chmod 700 "$WORK"
SAFE_DUMP="${WORK}/dump"

runuser -u postgres -- pg_restore --list "$SAFE_DUMP" >/dev/null \
  || die "dump illisible (tronqué ou d'un autre format que -Fc)."

if [[ $DRY_RUN -eq 1 ]]; then
  log "contenu du dump (aucune écriture) :"
  runuser -u postgres -- pg_restore --list "$SAFE_DUMP"
  exit 0
fi

if [[ "$TARGET_DB" == "$PROD_DB" && $FORCE -ne 1 ]]; then
  die "cible = base de production (${PROD_DB}). Ajouter --force en toute conscience."
fi

db_exists() {
  [[ "$(runuser -u postgres -- psql -tAc \
        "SELECT 1 FROM pg_database WHERE datname='$1'")" == "1" ]]
}

if db_exists "$TARGET_DB"; then
  if [[ $DROP_EXISTING -eq 1 ]]; then
    [[ "$TARGET_DB" != "$PROD_DB" || $FORCE -eq 1 ]] \
      || die "refus de supprimer la base de production."
    log "suppression de ${TARGET_DB}"
    # Les sessions ouvertes empêchent le DROP : on les coupe d'abord.
    runuser -u postgres -- psql -v ON_ERROR_STOP=1 -c \
      "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${TARGET_DB}'" >/dev/null
    runuser -u postgres -- dropdb "$TARGET_DB"
    runuser -u postgres -- createdb "$TARGET_DB"
  fi
else
  [[ $CREATE -eq 1 || $DROP_EXISTING -eq 1 ]] \
    || die "la base ${TARGET_DB} n'existe pas (ajouter --create)."
  log "création de ${TARGET_DB}"
  runuser -u postgres -- createdb "$TARGET_DB"
fi

# Les rôles ne sont pas dans le dump (pg_dump d'une seule base) : sans eux,
# pg_restore échoue sur chaque GRANT ... TO miara_app. On les crée sans mot de
# passe (NOLOGIN implicite via ALTER si besoin) uniquement s'ils manquent.
for role in miara_admin miara_app; do
  if [[ "$(runuser -u postgres -- psql -tAc \
        "SELECT 1 FROM pg_roles WHERE rolname='${role}'")" != "1" ]]; then
    log "rôle ${role} absent : création sans droit de connexion"
    runuser -u postgres -- psql -v ON_ERROR_STOP=1 -c "CREATE ROLE ${role} NOLOGIN" >/dev/null
  fi
done

log "restauration de ${SAFE_DUMP} dans ${TARGET_DB}"
# --clean --if-exists : la cible peut contenir un schéma partiel d'un essai
# précédent. --no-owner est volontairement ABSENT : on veut vérifier que les
# propriétaires et les politiques RLS reviennent tels quels.
# --exit-on-error : une restauration à moitié réussie est un piège, on préfère
# un échec net.
runuser -u postgres -- pg_restore \
  --clean --if-exists --exit-on-error \
  --dbname "$TARGET_DB" "$SAFE_DUMP"

log "restauration terminée, contrôles :"
runuser -u postgres -- psql -d "$TARGET_DB" -c \
  "SELECT count(*) AS tables FROM information_schema.tables WHERE table_schema='public'"
# Le vrai critère de réussite pour ce projet : les politiques RLS sont revenues,
# et les tables métier sont bien en FORCE RLS (ADR-002).
runuser -u postgres -- psql -d "$TARGET_DB" -c \
  "SELECT count(*) AS politiques_rls FROM pg_policies WHERE schemaname='public'"
runuser -u postgres -- psql -d "$TARGET_DB" -c \
  "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class
   WHERE relkind='r' AND relnamespace='public'::regnamespace
     AND relforcerowsecurity IS FALSE AND relrowsecurity IS TRUE"

log "OK. Si la cible était jetable, la supprimer : sudo -u postgres dropdb ${TARGET_DB}"
