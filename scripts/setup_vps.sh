#!/usr/bin/env bash
#
# Provisionnement d'un VPS Ubuntu pour Miara : utilisateur de service,
# PostgreSQL 16, RabbitMQ, Redis, Node LTS, Python 3.12 + uv, nginx, certbot,
# units systemd, sauvegardes, journaux, pare-feu.
#
# Pas de Docker : choix assumé du projet (carte INFRA). Services natifs.
#
# IDEMPOTENT : chaque étape vérifie avant d'agir, le script peut être relancé
# après une correction sans dupliquer quoi que ce soit.
#
# Usage :
#   sudo MIARA_DOMAIN=miara.example.org LETSENCRYPT_EMAIL=ops@example.org \
#        DB_ADMIN_PASSWORD=... DB_APP_PASSWORD=... RABBITMQ_PASSWORD=... \
#        /srv/miara/scripts/setup_vps.sh
#
# Les mots de passe passés ici DOIVENT correspondre à ceux de /etc/miara/.env
# (DATABASE_URL, DATABASE_URL_ADMIN, RABBITMQ_URL). Le script ne les écrit
# jamais dans le dépôt ni dans un journal.
set -euo pipefail

# --- Paramètres ------------------------------------------------------------
APP_USER="${APP_USER:-miara}"
APP_DIR="${APP_DIR:-/srv/miara}"
ENV_DIR="${ENV_DIR:-/etc/miara}"
ENV_FILE="${ENV_FILE:-${ENV_DIR}/.env}"
STORAGE_DIR="${STORAGE_DIR:-/var/lib/miara/storage}"
LOG_DIR="${LOG_DIR:-/var/log/miara}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/miara}"
ACME_WEBROOT="${ACME_WEBROOT:-/var/www/certbot}"

DB_NAME="${DB_NAME:-miara}"
DB_ADMIN_USER="${DB_ADMIN_USER:-miara_admin}"
DB_APP_USER="${DB_APP_USER:-miara_app}"
DB_ADMIN_PASSWORD="${DB_ADMIN_PASSWORD:-}"
DB_APP_PASSWORD="${DB_APP_PASSWORD:-}"
PG_VERSION="${PG_VERSION:-16}"

RABBITMQ_USER="${RABBITMQ_USER:-miara}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-}"
RABBITMQ_VHOST="${RABBITMQ_VHOST:-miara}"

NODE_MAJOR="${NODE_MAJOR:-22}"
MIARA_DOMAIN="${MIARA_DOMAIN:-}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-}"

# Ports FIXES du projet (CLAUDE.md), en dev comme en prod. Ils ne sont pas
# ouverts au pare-feu : nginx est le seul point d'entrée.
API_PORT=8010
WEB_PORT=3010

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
DEPLOY_DIR="${REPO_DIR}/deploy"

log()  { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
info() { printf '   %s\n' "$*"; }
die()  { printf '\033[31mERREUR: %s\033[0m\n' "$*" >&2; exit 1; }

require_root() {
  [[ $EUID -eq 0 ]] || die "à lancer avec sudo."
}

check_repo_location() {
  # Les units systemd, la tâche cron et les droits sudo référencent des chemins
  # absolus sous ${APP_DIR}. Si le dépôt est ailleurs, tout s'installera mais
  # rien ne démarrera : autant le dire tout de suite.
  if [[ "$REPO_DIR" != "$APP_DIR" ]]; then
    printf '\033[33mATTENTION: le dépôt est dans %s alors que les services attendent %s.\033[0m\n' \
      "$REPO_DIR" "$APP_DIR" >&2
    printf '  Déplacer le dépôt, ou relancer avec APP_DIR=%s.\n' "$REPO_DIR" >&2
  fi
}

# --- Paquets ---------------------------------------------------------------
apt_install() {
  # `apt-get install` est déjà idempotent, mais on évite le bruit et les
  # reconfigurations inutiles en filtrant ce qui est déjà présent.
  local missing=()
  local pkg
  for pkg in "$@"; do
    dpkg -s "$pkg" &>/dev/null || missing+=("$pkg")
  done
  if [[ ${#missing[@]} -eq 0 ]]; then
    info "déjà installés : $*"
    return
  fi
  info "installation : ${missing[*]}"
  apt-get install -y -qq "${missing[@]}"
}

ensure_base_packages() {
  log "Paquets de base"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt_install ca-certificates curl gnupg git make jq rsync ufw \
              nginx certbot python3-certbot-nginx \
              rabbitmq-server redis-server logrotate
}

ensure_python() {
  log "Python 3.12 + uv"
  # Ubuntu 24.04 fournit python3.12 dans les dépôts ; sur une autre version on
  # laisse uv installer l'interpréteur (le projet exige >= 3.12, pyproject).
  if apt-cache policy python3.12 2>/dev/null | grep -q 'Candidate: [0-9]'; then
    apt_install python3.12 python3.12-venv
  else
    info "python3.12 absent des dépôts : uv gérera l'interpréteur"
  fi

  if command -v uv &>/dev/null; then
    info "uv déjà présent ($(uv --version))"
  else
    # Installation à l'échelle du système : les units systemd et le script de
    # déploiement doivent trouver uv sans dépendre du PATH d'un shell de login.
    info "installation de uv dans /usr/local/bin"
    curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin INSTALLER_NO_MODIFY_PATH=1 sh
  fi
}

ensure_node() {
  log "Node.js LTS ${NODE_MAJOR}"
  if command -v node &>/dev/null && [[ "$(node --version)" == v${NODE_MAJOR}.* ]]; then
    info "node $(node --version) déjà installé"
    return
  fi
  # Dépôt NodeSource : la version de Node des dépôts Ubuntu est trop ancienne
  # pour Next.js 16 (>= 20.9 requis, on prend la LTS courante).
  local keyring=/usr/share/keyrings/nodesource.gpg
  if [[ ! -f $keyring ]]; then
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
      | gpg --dearmor -o "$keyring"
  fi
  echo "deb [signed-by=${keyring}] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" \
    > /etc/apt/sources.list.d/nodesource.list
  apt-get update -qq
  apt-get install -y -qq nodejs
  info "node $(node --version), npm $(npm --version)"
}

# --- Utilisateur et arborescence ------------------------------------------
ensure_user() {
  log "Utilisateur de service ${APP_USER}"
  if id -u "$APP_USER" &>/dev/null; then
    info "utilisateur ${APP_USER} existe déjà"
  else
    # Compte système sans mot de passe : il ne sert qu'à faire tourner les
    # services et à dérouler les déploiements, jamais à se connecter en SSH.
    useradd --system --create-home --home-dir "/home/${APP_USER}" \
            --shell /usr/sbin/nologin "$APP_USER"
    info "utilisateur ${APP_USER} créé"
  fi
}

ensure_directories() {
  log "Arborescence"
  install -d -o "$APP_USER" -g "$APP_USER" -m 755 "$APP_DIR"
  # Secrets : lisibles par le groupe du service, jamais par le reste du monde.
  install -d -o root -g "$APP_USER" -m 750 "$ENV_DIR"
  # CV déposés = données personnelles : accès strictement réservé au service.
  install -d -o "$APP_USER" -g "$APP_USER" -m 700 "$STORAGE_DIR"
  install -d -o root -g "$APP_USER" -m 775 "$LOG_DIR"
  # Sauvegardes : contiennent toute la base, donc root seul.
  install -d -o root -g root -m 700 "$BACKUP_DIR"
  install -d -o root -g root -m 755 "$ACME_WEBROOT"

  if [[ -f "$ENV_FILE" ]]; then
    chown root:"$APP_USER" "$ENV_FILE"
    chmod 640 "$ENV_FILE"
    info "${ENV_FILE} présent (droits corrigés en 640 root:${APP_USER})"
  else
    install -o root -g "$APP_USER" -m 640 "${DEPLOY_DIR}/.env.example" "$ENV_FILE"
    info "${ENV_FILE} créé depuis deploy/.env.example — À COMPLÉTER avant le premier démarrage"
  fi
}

# --- PostgreSQL ------------------------------------------------------------
ensure_postgres() {
  log "PostgreSQL ${PG_VERSION}"
  if ! apt-cache policy "postgresql-${PG_VERSION}" 2>/dev/null | grep -q 'Candidate: [0-9]'; then
    # La version demandée n'est pas dans les dépôts de cette version d'Ubuntu :
    # on ajoute PGDG plutôt que d'accepter silencieusement une autre version
    # majeure. Le défaut est 16 (carte INFRA) ; la machine de développement
    # tourne sur PostgreSQL 18, d'où la variable PG_VERSION, à aligner sur le
    # dev si on veut exactement le même moteur qu'en test (PG_VERSION=18).
    info "ajout du dépôt PGDG (postgresql-${PG_VERSION} introuvable)"
    install -d -m 755 /usr/share/postgresql-common/pgdg
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
      -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
    local codename
    # shellcheck disable=SC1091  # fichier système, absent au moment de l'analyse
    codename="$(. /etc/os-release && echo "$VERSION_CODENAME")"
    echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] http://apt.postgresql.org/pub/repos/apt ${codename}-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list
    apt-get update -qq
  fi
  apt_install "postgresql-${PG_VERSION}" postgresql-client-common

  local conf="/etc/postgresql/${PG_VERSION}/main/postgresql.conf"
  if [[ -f $conf ]]; then
    # PostgreSQL ne doit jamais écouter sur l'interface publique : le pare-feu
    # est une seconde barrière, pas la première.
    if grep -qE "^listen_addresses *= *'localhost'" "$conf"; then
      info "listen_addresses déjà limité à localhost"
    else
      sed -i "s/^#\?listen_addresses *=.*/listen_addresses = 'localhost'/" "$conf"
      info "listen_addresses forcé à localhost"
      systemctl restart "postgresql@${PG_VERSION}-main" || systemctl restart postgresql
    fi
  fi
  systemctl enable --now postgresql
}

psql_admin() { sudo -u postgres psql -v ON_ERROR_STOP=1 "$@"; }

role_exists() {
  [[ "$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$1'")" == "1" ]]
}

ensure_role() {
  # $1 rôle, $2 mot de passe, $3 attributs (BYPASSRLS / NOBYPASSRLS)
  local role="$1" password="$2" attrs="$3"
  if [[ -z "$password" ]]; then
    role_exists "$role" \
      && { info "${role} : mot de passe non fourni, rôle laissé tel quel"; return; }
    die "${role} n'existe pas et aucun mot de passe n'a été fourni (variable d'env)."
  fi
  if role_exists "$role"; then
    psql_admin -c "ALTER ROLE ${role} LOGIN ${attrs} PASSWORD '${password}'" >/dev/null
    info "rôle ${role} mis à jour"
  else
    psql_admin -c "CREATE ROLE ${role} LOGIN ${attrs} PASSWORD '${password}'" >/dev/null
    info "rôle ${role} créé"
  fi
}

ensure_database() {
  log "Base et rôles applicatifs"
  # Deux rôles distincts (ADR-002) :
  #  - miara_admin : propriétaire du schéma, BYPASSRLS, réservé aux migrations ;
  #  - miara_app   : runtime, NOBYPASSRLS, soumis aux politiques FORCE RLS.
  # Le runtime ne doit JAMAIS utiliser miara_admin, sinon l'isolation
  # multi-locataire tombe sans qu'aucun test ne le signale.
  ensure_role "$DB_ADMIN_USER" "$DB_ADMIN_PASSWORD" "BYPASSRLS"
  ensure_role "$DB_APP_USER"   "$DB_APP_PASSWORD"   "NOBYPASSRLS"

  if [[ "$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'")" == "1" ]]; then
    info "base ${DB_NAME} existe déjà"
  else
    sudo -u postgres createdb -O "$DB_ADMIN_USER" "$DB_NAME"
    info "base ${DB_NAME} créée (propriétaire ${DB_ADMIN_USER})"
  fi

  psql_admin -c "ALTER DATABASE ${DB_NAME} OWNER TO ${DB_ADMIN_USER}" >/dev/null
  psql_admin -d "$DB_NAME" -c "ALTER SCHEMA public OWNER TO ${DB_ADMIN_USER}" >/dev/null
  # miara_app n'obtient QUE USAGE ici. Les droits table par table sont
  # accordés par les migrations Alembic, en même temps que les politiques RLS :
  # un GRANT global ici masquerait l'oubli d'un GRANT dans une migration.
  psql_admin -d "$DB_NAME" -c "GRANT USAGE ON SCHEMA public TO ${DB_APP_USER}" >/dev/null
  psql_admin -d "$DB_NAME" -c "REVOKE CREATE ON SCHEMA public FROM PUBLIC" >/dev/null
  info "droits de schéma alignés (USAGE pour ${DB_APP_USER}, CREATE retiré à PUBLIC)"
}

# --- Broker et cache -------------------------------------------------------
ensure_rabbitmq() {
  log "RabbitMQ"
  # Écoute restreinte à la loopback : le broker n'a aucune raison d'être
  # joignable de l'extérieur, et son AMQP n'est pas chiffré ici.
  local conf=/etc/rabbitmq/rabbitmq.conf
  local wanted="listeners.tcp.1 = 127.0.0.1:5672"
  if [[ -f $conf ]] && grep -qF "$wanted" "$conf"; then
    info "listener déjà limité à 127.0.0.1"
  else
    touch "$conf"
    sed -i '/^listeners\.tcp\.1/d' "$conf"
    printf '%s\n' "$wanted" >> "$conf"
    info "listener limité à 127.0.0.1"
    systemctl restart rabbitmq-server
  fi
  systemctl enable --now rabbitmq-server

  if [[ -z "$RABBITMQ_PASSWORD" ]]; then
    info "RABBITMQ_PASSWORD non fourni : utilisateur applicatif non créé"
    return
  fi
  if rabbitmqctl list_users 2>/dev/null | grep -qE "^${RABBITMQ_USER}\b"; then
    rabbitmqctl change_password "$RABBITMQ_USER" "$RABBITMQ_PASSWORD" >/dev/null
    info "utilisateur ${RABBITMQ_USER} : mot de passe mis à jour"
  else
    rabbitmqctl add_user "$RABBITMQ_USER" "$RABBITMQ_PASSWORD" >/dev/null
    info "utilisateur ${RABBITMQ_USER} créé"
  fi
  rabbitmqctl list_vhosts 2>/dev/null | grep -qE "^${RABBITMQ_VHOST}$" \
    || rabbitmqctl add_vhost "$RABBITMQ_VHOST" >/dev/null
  rabbitmqctl set_permissions -p "$RABBITMQ_VHOST" "$RABBITMQ_USER" ".*" ".*" ".*" >/dev/null
  # `guest` ne sert qu'aux essais locaux : le laisser actif en production est
  # un compte par défaut de plus à surveiller.
  rabbitmqctl list_users 2>/dev/null | grep -qE '^guest\b' \
    && rabbitmqctl delete_user guest >/dev/null && info "utilisateur guest supprimé"
  info "vhost ${RABBITMQ_VHOST} et permissions en place"
}

ensure_redis() {
  log "Redis"
  local conf=/etc/redis/redis.conf
  if [[ -f $conf ]]; then
    if grep -qE '^bind 127\.0\.0\.1 -::1' "$conf"; then
      info "bind déjà limité à la loopback"
    else
      sed -i 's/^bind .*/bind 127.0.0.1 -::1/' "$conf"
      info "bind limité à la loopback"
      systemctl restart redis-server
    fi
  fi
  systemctl enable --now redis-server
}

# --- Fichiers de configuration système ------------------------------------
install_if_changed() {
  # $1 source, $2 destination, $3 mode. Ne touche au fichier (et donc à sa
  # date) que s'il a réellement changé : les `systemctl daemon-reload` et
  # autres rechargements restent conditionnés à un vrai changement.
  local src="$1" dst="$2" mode="${3:-644}"
  if [[ -f "$dst" ]] && cmp -s "$src" "$dst"; then
    return 1
  fi
  install -o root -g root -m "$mode" "$src" "$dst"
  return 0
}

install_systemd_units() {
  log "Units systemd"
  local changed=0 unit
  for unit in miara-api miara-worker-heavy miara-worker-light miara-web; do
    if install_if_changed "${DEPLOY_DIR}/systemd/${unit}.service" \
                          "/etc/systemd/system/${unit}.service" 644; then
      info "${unit}.service installé/mis à jour"
      changed=1
    else
      info "${unit}.service inchangé"
    fi
  done
  # Le répertoire n'existe pas par défaut sur Ubuntu : sans ce install -d,
  # l'installation du fichier échoue (et le script s'arrête sur set -e).
  install -d -m 755 /etc/systemd/journald.conf.d
  if install_if_changed "${DEPLOY_DIR}/journald/miara.conf" \
                        /etc/systemd/journald.conf.d/miara.conf 644; then
    info "configuration journald mise à jour"
    systemctl restart systemd-journald
  fi
  [[ $changed -eq 1 ]] && systemctl daemon-reload
  # enable sans --now : au premier passage /etc/miara/.env n'est pas encore
  # renseigné et le venv n'existe pas. C'est deploy.sh qui démarre les services.
  systemctl enable miara-api miara-worker-heavy miara-worker-light miara-web >/dev/null
  info "services activés au démarrage (non démarrés ici)"
}

install_support_files() {
  log "Journaux, sauvegardes, sudoers"
  install_if_changed "${DEPLOY_DIR}/logrotate/miara" /etc/logrotate.d/miara 644 \
    && info "logrotate installé"
  install_if_changed "${DEPLOY_DIR}/cron/miara-backup" /etc/cron.d/miara-backup 644 \
    && info "tâche cron de sauvegarde installée"
  install -d -m 755 /etc/letsencrypt/renewal-hooks/deploy
  install_if_changed "${DEPLOY_DIR}/certbot/reload-nginx.sh" \
                     /etc/letsencrypt/renewal-hooks/deploy/miara-reload-nginx.sh 755 \
    && info "hook de rechargement nginx installé"

  # sudoers : on valide AVANT d'installer. Un fichier invalide dans
  # /etc/sudoers.d casse sudo pour toute la machine.
  local tmp
  tmp="$(mktemp)"
  cp "${DEPLOY_DIR}/sudoers/miara-deploy" "$tmp"
  if visudo -cqf "$tmp"; then
    install -o root -g root -m 440 "$tmp" /etc/sudoers.d/miara-deploy
    info "droits sudo de déploiement installés"
  else
    rm -f "$tmp"
    die "deploy/sudoers/miara-deploy est invalide, installation annulée."
  fi
  rm -f "$tmp"
}

# --- nginx et TLS ----------------------------------------------------------
nginx_reload_if_valid() {
  # On ne recharge jamais nginx sans `nginx -t` : une conf invalide laisserait
  # le site hors ligne alors que l'ancien processus tournait très bien.
  if nginx -t; then
    systemctl reload nginx
    return 0
  fi
  die "configuration nginx invalide, rechargement annulé."
}

install_nginx_vhost() {
  # $1 = fichier source (bootstrap ou production)
  local src="$1" dst=/etc/nginx/sites-available/miara.conf
  local tmp
  tmp="$(mktemp)"
  sed "s/__DOMAIN__/${MIARA_DOMAIN}/g" "$src" > "$tmp"
  if [[ -f "$dst" ]] && cmp -s "$tmp" "$dst"; then
    info "vhost inchangé"
    rm -f "$tmp"
    return
  fi
  install -o root -g root -m 644 "$tmp" "$dst"
  rm -f "$tmp"
  ln -sfn "$dst" /etc/nginx/sites-enabled/miara.conf
  # Le vhost par défaut capterait les requêtes sur l'IP nue et masquerait
  # une erreur de server_name.
  rm -f /etc/nginx/sites-enabled/default
  install_if_changed "${DEPLOY_DIR}/nginx/map-connection-upgrade.conf" \
                     /etc/nginx/conf.d/miara-upgrade.conf 644 >/dev/null || true
  nginx_reload_if_valid
  info "vhost $(basename "$src") activé pour ${MIARA_DOMAIN}"
}

ensure_nginx_and_tls() {
  log "nginx et TLS"
  [[ -n "$MIARA_DOMAIN" ]] || die "MIARA_DOMAIN est obligatoire (nom DNS public)."
  systemctl enable --now nginx

  local live="/etc/letsencrypt/live/${MIARA_DOMAIN}/fullchain.pem"
  if [[ -f "$live" ]]; then
    info "certificat déjà présent pour ${MIARA_DOMAIN}"
  else
    # Ordre imposé par le poulet et l'œuf : le vhost de production référence
    # des certificats qui n'existent pas encore, donc on passe d'abord par le
    # vhost de bootstrap pour servir le challenge HTTP-01.
    install_nginx_vhost "${DEPLOY_DIR}/nginx/miara-bootstrap.conf"
    [[ -n "$LETSENCRYPT_EMAIL" ]] \
      || die "LETSENCRYPT_EMAIL est obligatoire pour émettre le certificat."
    info "demande de certificat pour ${MIARA_DOMAIN}"
    certbot certonly --webroot -w "$ACME_WEBROOT" \
      -d "$MIARA_DOMAIN" \
      --non-interactive --agree-tos -m "$LETSENCRYPT_EMAIL" \
      --keep-until-expiring
  fi
  install_nginx_vhost "${DEPLOY_DIR}/nginx/miara.conf"

  # Le paquet certbot installe un timer systemd ; on s'assure juste qu'il
  # tourne. Le renouvellement lui-même est testé par `certbot renew --dry-run`.
  systemctl enable --now certbot.timer 2>/dev/null \
    || info "certbot.timer absent : vérifier /etc/cron.d/certbot"
}

# --- Pare-feu --------------------------------------------------------------
ensure_firewall() {
  log "Pare-feu (ufw)"
  # SSH d'abord, TOUJOURS : activer ufw avant d'autoriser le 22 coupe la
  # session en cours et rend le VPS inaccessible.
  ufw allow 22/tcp    >/dev/null
  ufw allow 80/tcp    >/dev/null
  ufw allow 443/tcp   >/dev/null
  ufw default deny incoming  >/dev/null
  ufw default allow outgoing >/dev/null
  # PostgreSQL (5432), RabbitMQ (5672) et Redis (6379) ne sont PAS ouverts :
  # ils écoutent sur la loopback (cf. ensure_postgres/rabbitmq/redis), ce qui
  # est plus sûr qu'une règle de filtrage qu'on peut relâcher par erreur.
  # Les ports applicatifs 8010 et 3010 restent eux aussi fermés : nginx seul.
  ufw --force enable >/dev/null
  info "règles actives : 22, 80, 443 ; 5432/5672/6379 en loopback uniquement"
  ufw status verbose | sed 's/^/   /'
}

summary() {
  log "Terminé"
  cat <<EOS
   Étapes suivantes (manuelles, volontairement) :

   1. Compléter ${ENV_FILE} (voir deploy/.env.example pour chaque variable).
   2. Vérifier que le dépôt est bien dans ${APP_DIR} et appartient à ${APP_USER} :
        sudo chown -R ${APP_USER}:${APP_USER} ${APP_DIR}
   3. Premier déploiement :
        sudo -u ${APP_USER} ${APP_DIR}/scripts/deploy.sh
   4. Vérifications :
        curl -fsS https://${MIARA_DOMAIN}/health
        sudo certbot renew --dry-run
        sudo /srv/miara/scripts/backup_db.sh

   Ports internes : API ${API_PORT}, web ${WEB_PORT} (loopback, non ouverts).
EOS
}

main() {
  require_root
  check_repo_location
  ensure_base_packages
  ensure_user
  ensure_directories
  ensure_python
  ensure_node
  ensure_postgres
  ensure_database
  ensure_rabbitmq
  ensure_redis
  install_systemd_units
  install_support_files
  ensure_nginx_and_tls
  ensure_firewall
  summary
}

main "$@"
