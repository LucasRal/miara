#!/usr/bin/env bash
#
# Sauvegarde quotidienne de la base Miara (appelé par /etc/cron.d/miara-backup).
#
#   sudo /srv/miara/scripts/backup_db.sh            # sauvegarde immédiate
#
# Choix : le dump est pris par l'utilisateur système `postgres` (authentification
# peer, donc AUCUN mot de passe à stocker pour la sauvegarde) et non par
# miara_admin sur TCP. Un secret de moins sur le disque.
#
# Format `custom` (-Fc) : compressé, et surtout restaurable table par table avec
# pg_restore, ce qu'un dump SQL brut ne permet pas.
set -euo pipefail

# Réglages surchargeables par /etc/miara/backup.env (facultatif, sans secret).
BACKUP_ENV="${BACKUP_ENV:-/etc/miara/backup.env}"
if [[ -r "$BACKUP_ENV" ]]; then
  # shellcheck disable=SC1090  # chemin connu à l'exécution seulement
  source "$BACKUP_ENV"
fi

DB_NAME="${DB_NAME:-miara}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/miara}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
# Seuil d'alerte : un dump anormalement petit signale une base vide ou un dump
# interrompu. 20 ko est déjà en dessous de la taille d'un schéma seul.
MIN_SIZE_BYTES="${MIN_SIZE_BYTES:-20480}"

log() { printf '%s [backup] %s\n' "$(date -Is)" "$*"; }
die() { printf '%s [backup] ERREUR: %s\n' "$(date -Is)" "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "à lancer en root (cron l'appelle en root)."
id -u postgres &>/dev/null || die "utilisateur système postgres introuvable."

install -d -o root -g root -m 700 "$BACKUP_DIR"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="${BACKUP_DIR}/${DB_NAME}-${stamp}.dump"
tmp="${target}.partial"

# On écrit d'abord un `.partial` : si pg_dump ou le disque lâche en cours de
# route, la rotation ne verra jamais ce fichier comme une sauvegarde valide.
#
# pg_dump écrit sur sa SORTIE STANDARD, redirigée par root : `--file=` ferait
# ouvrir le fichier par l'utilisateur `postgres`, qui n'a aucun droit sur
# ${BACKUP_DIR} (0700 root:root). Rediriger depuis root garde le répertoire de
# sauvegarde fermé au lieu de l'ouvrir à postgres.
log "dump de ${DB_NAME} vers ${target}"
umask 077
if ! runuser -u postgres -- pg_dump --format=custom --compress=6 "$DB_NAME" > "$tmp"; then
  rm -f "$tmp"
  die "pg_dump a échoué, aucune sauvegarde produite."
fi

size="$(stat -c %s "$tmp")"
if (( size < MIN_SIZE_BYTES )); then
  rm -f "$tmp"
  die "dump suspect (${size} octets < ${MIN_SIZE_BYTES}), rejeté."
fi

mv "$tmp" "$target"
chmod 600 "$target"
log "sauvegarde OK : ${target} (${size} octets)"

# Vérification de lisibilité : pg_restore --list relit l'en-tête et le sommaire
# du dump. Ça ne prouve pas que les données sont bonnes, mais ça attrape le
# fichier tronqué — le cas le plus fréquent, et le plus douloureux.
# Même raison que pour le dump : c'est root qui ouvre le fichier et passe le
# descripteur à `postgres`, plutôt que de lui donner accès au répertoire.
if ! runuser -u postgres -- pg_restore --list >/dev/null < "$target"; then
  die "le dump n'est pas relisible par pg_restore : ${target}"
fi
log "sommaire pg_restore lisible"

# Rotation : 14 jours glissants (carte INFRA). -mtime +N compte en jours
# entiers révolus, d'où le N-1 pour ne pas garder un jour de trop.
deleted="$(find "$BACKUP_DIR" -maxdepth 1 -name "${DB_NAME}-*.dump" -type f \
  -mtime "+$((RETENTION_DAYS - 1))" -print -delete | wc -l)"
log "rotation : ${deleted} sauvegarde(s) de plus de ${RETENTION_DAYS} jours supprimée(s)"

# Orphelins d'une exécution interrompue : sans ça ils s'accumulent en silence.
find "$BACKUP_DIR" -maxdepth 1 -name '*.partial' -mtime +1 -delete

count="$(find "$BACKUP_DIR" -maxdepth 1 -name "${DB_NAME}-*.dump" -type f | wc -l)"
log "état : ${count} sauvegarde(s) présente(s) dans ${BACKUP_DIR}"
