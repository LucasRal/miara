#!/usr/bin/env bash
# Installe les services natifs requis par Miara sur Ubuntu (pas de Docker - ADR/carte INFRA)
# et crée la base PostgreSQL `miara` + son rôle. Idempotent : relançable sans risque.
#
# Usage :  sudo DB_PASSWORD=... ./scripts/setup_ubuntu.sh   (défaut dev : miara)
set -euo pipefail

DB_NAME="${DB_NAME:-miara}"
DB_USER="${DB_USER:-miara}"
DB_PASSWORD="${DB_PASSWORD:-miara}"
# Rôles séparés (carte CORE / ADR-002) : admin = migrations (BYPASSRLS),
# app = runtime, soumis aux politiques RLS (les tables sont en FORCE RLS).
ADMIN_USER="${ADMIN_USER:-miara_admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
APP_USER="${APP_USER:-miara_app}"
APP_PASSWORD="${APP_PASSWORD:-}"

if [[ $EUID -ne 0 ]]; then
  echo "Ce script doit être lancé avec sudo." >&2
  exit 1
fi

echo "== Paquets système =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
for pkg in postgresql rabbitmq-server redis-server; do
  if dpkg -s "$pkg" &>/dev/null; then
    echo "   $pkg déjà installé"
  else
    echo "   installation de $pkg..."
    apt-get install -y -qq "$pkg"
  fi
done

echo "== Services =="
for svc in postgresql rabbitmq-server redis-server; do
  systemctl enable --now "$svc"
  systemctl is-active --quiet "$svc" && echo "   $svc actif"
done

echo "== Base de données =="
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1; then
  echo "   rôle ${DB_USER} existe déjà"
else
  sudo -u postgres psql -c "CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}'"
  echo "   rôle ${DB_USER} créé"
fi
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
  echo "   base ${DB_NAME} existe déjà"
else
  sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"
  echo "   base ${DB_NAME} créée (owner ${DB_USER})"
fi

echo "== Rôles applicatifs (RLS) =="
create_or_update_role() {
  local role="$1" password="$2" extra="$3"
  if [[ -z "$password" ]]; then
    echo "   $role : mot de passe non fourni (variable d'env), rôle non modifié"
    return
  fi
  if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${role}'" | grep -q 1; then
    sudo -u postgres psql -c "ALTER ROLE ${role} LOGIN PASSWORD '${password}' ${extra}"
    echo "   rôle ${role} mis à jour"
  else
    sudo -u postgres psql -c "CREATE ROLE ${role} LOGIN PASSWORD '${password}' ${extra}"
    echo "   rôle ${role} créé"
  fi
}
create_or_update_role "${ADMIN_USER}" "${ADMIN_PASSWORD}" "BYPASSRLS"
create_or_update_role "${APP_USER}" "${APP_PASSWORD}" "NOBYPASSRLS"
if [[ -n "$ADMIN_PASSWORD" ]]; then
  sudo -u postgres psql -c "ALTER DATABASE ${DB_NAME} OWNER TO ${ADMIN_USER}" >/dev/null
  sudo -u postgres psql -d "${DB_NAME}" -c "ALTER SCHEMA public OWNER TO ${ADMIN_USER}" >/dev/null
  sudo -u postgres psql -d "${DB_NAME}" -c "GRANT USAGE ON SCHEMA public TO ${APP_USER}" >/dev/null
  echo "   base ${DB_NAME} : owner ${ADMIN_USER}, USAGE accordé à ${APP_USER}"
fi

echo
echo "Terminé. Renseigner backend/.env :"
echo "  DATABASE_URL=postgresql+asyncpg://${APP_USER}:<mdp app>@localhost:5432/${DB_NAME}"
echo "  DATABASE_URL_ADMIN=postgresql+asyncpg://${ADMIN_USER}:<mdp admin>@localhost:5432/${DB_NAME}"
