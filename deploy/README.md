# Déploiement Miara sur VPS (Ubuntu, sans Docker)

Cible : un VPS Ubuntu 24.04 servant l'application derrière nginx + TLS, avec
redémarrage automatique des services, sauvegarde quotidienne de la base et
mise à jour en une commande.

Pas de conteneurs : services natifs (choix du projet, carte INFRA). Un seul
déployable applicatif, découpé en quatre processus (ADR-001, ADR-006).

---

## 1. Ce qui est installé où

| Élément | Chemin sur le VPS | Source dans le dépôt |
| --- | --- | --- |
| Code | `/srv/miara` (propriétaire `miara`) | le dépôt lui-même |
| Secrets d'exécution | `/etc/miara/.env` (`640 root:miara`) | `deploy/.env.example` |
| Réglages de sauvegarde | `/etc/miara/backup.env` (facultatif) | `deploy/backup.env.example` |
| Services | `/etc/systemd/system/miara-*.service` | `deploy/systemd/` |
| vhost nginx | `/etc/nginx/sites-available/miara.conf` | `deploy/nginx/miara.conf` |
| `map` websocket nginx | `/etc/nginx/conf.d/miara-upgrade.conf` | `deploy/nginx/map-connection-upgrade.conf` |
| Rotation des journaux | `/etc/logrotate.d/miara` | `deploy/logrotate/miara` |
| Rétention journald | `/etc/systemd/journald.conf.d/miara.conf` | `deploy/journald/miara.conf` |
| Sauvegarde quotidienne | `/etc/cron.d/miara-backup` | `deploy/cron/miara-backup` |
| Hook de renouvellement TLS | `/etc/letsencrypt/renewal-hooks/deploy/miara-reload-nginx.sh` | `deploy/certbot/reload-nginx.sh` |
| Droits sudo de déploiement | `/etc/sudoers.d/miara-deploy` | `deploy/sudoers/miara-deploy` |
| CV déposés | `/var/lib/miara/storage` (`700 miara`) | — |
| Sauvegardes | `/var/backups/miara` (`700 root`) | — |
| Journaux disque | `/var/log/miara` | — |

### Processus

| Service | Rôle | Écoute |
| --- | --- | --- |
| `miara-api` | FastAPI/uvicorn, `API_WORKERS` (2 à 4) | `127.0.0.1:8010` |
| `miara-worker-heavy` | Celery `-Q heavy`, concurrence 4 (extraction, scoring LLM) | — |
| `miara-worker-light` | Celery `-Q light`, concurrence 2 (sync CRM, notifications) | — |
| `miara-web` | Next.js `next start` | `127.0.0.1:3010` |
| `nginx` | TLS, `/api/` → 8010, `/` → 3010 | `0.0.0.0:80`, `0.0.0.0:443` |

**Un worker par file, jamais un seul sur les deux.** `make worker` monte en
développement les mêmes deux processus, aux mêmes concurrences
(`WORKER_HEAVY_CONCURRENCY=4`, `WORKER_LIGHT_CONCURRENCY=2`). Un worker unique
abonné à `heavy,light` fait attendre les tâches légères derrière la notation :
mesuré le 22 septembre 2026, 3 sondes `core.ping` sur 5 perdues et p95 à
11,72 s contre 0,02 s avec deux workers (`bench/reports/20260922-155013` et
`20260922-155731`, voir ADR-006).

**Ports : 8010 (backend) et 3010 (frontend), en production comme en
développement** — c'est une règle du projet (`CLAUDE.md`). La carte Trello
mentionnait 8000/3000 ; l'écart est assumé et volontaire. Ces deux ports ne
sont pas ouverts au pare-feu : ils n'écoutent que sur la loopback, nginx est
le seul point d'entrée.

---

## 2. Installation initiale

```bash
# 1. Le dépôt doit être en place AVANT le provisionnement : le script installe
#    des fichiers qui en proviennent, et tout référence /srv/miara.
sudo git clone <url-du-dépôt> /srv/miara

# 2. Provisionnement (idempotent, relançable). Crée l'utilisateur miara,
#    installe les services, obtient le certificat, active le pare-feu.
sudo MIARA_DOMAIN=miara.example.org \
     LETSENCRYPT_EMAIL=ops@example.org \
     DB_ADMIN_PASSWORD='...' \
     DB_APP_PASSWORD='...' \
     RABBITMQ_PASSWORD='...' \
     /srv/miara/scripts/setup_vps.sh

# 3. Le dépôt a été cloné en root : le rendre au service.
sudo chown -R miara:miara /srv/miara

# 4. Renseigner les secrets (le script a déposé un gabarit).
sudo nano /etc/miara/.env      # cf. deploy/.env.example, chaque variable est commentée

# 5. Premier déploiement.
sudo -u miara /srv/miara/scripts/deploy.sh
```

Les mots de passe passés à `setup_vps.sh` **doivent** être ceux écrits dans
`DATABASE_URL`, `DATABASE_URL_ADMIN` et `RABBITMQ_URL` de `/etc/miara/.env`.
Le script ne les déduit pas et ne les écrit nulle part.

Ce que fait `setup_vps.sh`, dans l'ordre : paquets de base → utilisateur
`miara` → arborescence → Python 3.12 + `uv` (dans `/usr/local/bin`) → Node LTS
(NodeSource) → PostgreSQL 16 (variable `PG_VERSION` ; dépôt PGDG si la
version demandée manque aux dépôts, voir §9) → base et rôles →
RabbitMQ → Redis → units systemd → logrotate/cron/sudoers → nginx + certificat
→ ufw. Chaque étape vérifie l'état avant d'agir ; relancer le script après
correction d'une variable est le mode d'emploi normal.

---

## 3. Mise à jour et retour arrière

```bash
sudo -u miara /srv/miara/scripts/deploy.sh
```

Enchaîne : `git fetch`/`pull --ff-only` → `uv sync --frozen --no-dev` →
`alembic upgrade head` → `npm ci && npm run build` → `systemctl restart` des
quatre services → attente de `/health` (backend, puis frontend).
Toute la sortie est archivée dans `/var/log/miara/deploy.log`.

Retour arrière :

```bash
sudo -u miara /srv/miara/scripts/deploy.sh --ref <sha-précédent>
```

Le SHA précédent est affiché au début et à la fin de chaque déploiement, et
rappelé en cas d'échec. Le retour arrière emprunte **le même chemin de code**
que le déploiement normal (checkout détaché + rejeu complet).

**Limite connue, assumée :** un retour arrière du code n'annule pas une
migration Alembic déjà appliquée. Avant de revenir en arrière sur une
révision antérieure à une migration destructive, vérifier si le code visé
tolère le schéma courant ; sinon, `alembic downgrade <révision>` d'abord.
Écrire les migrations de façon additive (ajouter, puis nettoyer au déploiement
suivant) évite ce cas presque toujours.

**Interruption de service :** `next build` réécrit `.next` pendant que
l'ancien serveur tourne, et les quatre services redémarrent ensemble. Compter
quelques secondes d'indisponibilité par déploiement. C'est acceptable pour ce
projet ; une mise à jour sans coupure demanderait deux répertoires de version
et un basculement de symlink.

---

## 4. Variables d'environnement

Toutes les variables attendues par `/etc/miara/.env` sont listées et
commentées dans **`deploy/.env.example`**. Points qui méritent attention :

- `DATABASE_URL` → rôle **`miara_app`**, soumis aux politiques RLS. C'est la
  seule URL utilisée par l'API et les workers.
- `DATABASE_URL_ADMIN` → rôle **`miara_admin`** (BYPASSRLS), lu uniquement par
  `alembic/env.py`. Ne jamais le donner au runtime : l'isolation
  multi-locataire tomberait sans qu'aucun test ne l'indique (ADR-002).
- `ALLOWED_ORIGINS` doit valoir exactement l'origine publique en `https`.
- `COOKIE_SECURE=true` dès qu'on est derrière TLS.
- `SF_REDIRECT_URI` doit correspondre au caractère près à la Callback URL de
  la Connected App Salesforce, donc pointer sur le domaine public en `https`.
- `NEXT_PUBLIC_*` est figée **au build** : la changer impose un redéploiement
  complet, un simple `systemctl restart miara-web` ne suffira pas.
- `API_WORKERS`, `WORKER_HEAVY_CONCURRENCY`, `WORKER_LIGHT_CONCURRENCY` sont
  lues par les units systemd via `EnvironmentFile`.

En production il n'y a **pas** de `backend/.env` : pydantic-settings lit
l'environnement du processus, que systemd remplit depuis `/etc/miara/.env`.
Si un `backend/.env` traîne sur le serveur, il prendra le pas sur rien du tout
mais brouillera le diagnostic — le supprimer.

---

## 5. TLS

Certificat émis par `certbot certonly --webroot` (racine `/var/www/certbot`),
via un vhost de bootstrap en HTTP seul — le vhost de production référence des
fichiers de certificat qui n'existent pas encore au premier passage, nginx
refuserait de démarrer.

Renouvellement : `certbot.timer` (installé par le paquet). Le hook
`/etc/letsencrypt/renewal-hooks/deploy/miara-reload-nginx.sh` recharge nginx
après chaque renouvellement — sans lui, nginx continuerait à servir l'ancien
certificat jusqu'à son expiration.

Vérifications :

```bash
sudo certbot certificates
sudo certbot renew --dry-run
systemctl list-timers certbot.timer
```

---

## 6. Sauvegardes et restauration

Sauvegarde : `/etc/cron.d/miara-backup` lance `scripts/backup_db.sh` chaque
jour à 03h17 UTC. Le dump est pris par l'utilisateur système `postgres`
(authentification peer) : **aucun mot de passe de sauvegarde n'est stocké**.
Format `custom` (`pg_dump -Fc`), fichiers dans `/var/backups/miara`, rotation
à 14 jours. Le script écrit d'abord un `.partial`, refuse un dump plus petit
que `MIN_SIZE_BYTES`, puis relit le sommaire avec `pg_restore --list` avant de
valider la sauvegarde.

Déclencher une sauvegarde à la main :

```bash
sudo /srv/miara/scripts/backup_db.sh
ls -lh /var/backups/miara
```

### Tester la restauration sur une base jetable

Cette procédure a été déroulée en entier sur la machine de développement
(PostgreSQL 18, base `miara` de dev) : voir §9. Elle ne touche jamais la base
de production : la cible par défaut du script est `miara_restore_test`, et une
restauration sur `miara` exige `--force`.

```bash
# 1. Inspection seule, aucune écriture : on vérifie que le dump est lisible.
sudo /srv/miara/scripts/restore_db.sh --dry-run

# 2. Restauration dans une base jetable, créée pour l'occasion.
sudo /srv/miara/scripts/restore_db.sh --create --into miara_restore_test

# 3. Contrôles (le script les affiche déjà) : nombre de tables, nombre de
#    politiques RLS, et liste des tables qui auraient perdu le FORCE RLS.
sudo -u postgres psql -d miara_restore_test -c \
  "SELECT count(*) FROM pg_policies WHERE schemaname='public'"

# 4. Contrôle métier : l'isolation tient-elle encore ? Une requête sans
#    app.current_org ne doit rien renvoyer d'une table multi-locataire.
#    Prendre une table PORTEUSE d'une politique (llm_calls, candidate_scores,
#    conversations...) : `organizations` n'en a pas, elle répondrait et on
#    croirait à tort que le RLS est tombé.
sudo -u postgres psql -d miara_restore_test -c \
  "SET ROLE miara_app; SELECT count(*) FROM llm_calls;"

# 5. Ménage.
sudo -u postgres dropdb miara_restore_test
```

Note : le dump d'une base ne contient pas les rôles. `restore_db.sh` recrée
`miara_admin` et `miara_app` en `NOLOGIN` s'ils manquent, faute de quoi chaque
`GRANT ... TO miara_app` du dump échouerait. Sur un VPS de secours vierge, il
faudra ensuite leur redonner un mot de passe (`ALTER ROLE ... LOGIN PASSWORD`).

**Ce que la sauvegarde ne couvre pas :** les CV déposés dans
`/var/lib/miara/storage` (données personnelles, hors base) et `/etc/miara/.env`.
Les inclure dans une sauvegarde hors machine est un travail à part entière —
notamment parce qu'ils contiennent des données personnelles et des secrets, et
ne peuvent pas être stockés comme le dump SQL.

---

## 7. Journaux

- API, workers et frontend écrivent sur stdout/stderr → **journald**
  (`SyslogIdentifier` = nom du service). Les lignes du backend sont du JSON
  structlog avec `request_id`.
- `deploy/journald/miara.conf` rend les journaux persistants et les borne
  (1 Go, 30 jours) : sans `Storage=persistent`, un redémarrage efface
  justement les traces de l'incident qui l'a provoqué.
- `logrotate` ne gère que les fichiers disque (`/var/log/miara/*.log` :
  déploiements et sauvegardes), 14 rotations quotidiennes compressées.
- nginx conserve ses propres journaux (`/var/log/nginx/miara.*.log`) avec la
  rotation fournie par son paquet.

```bash
journalctl -u miara-api -f
journalctl -u miara-worker-heavy --since "1 hour ago"
journalctl -u miara-api --since today | jq -r 'select(.level=="error")'
tail -f /var/log/miara/deploy.log
```

---

## 8. Dépannage

| Symptôme | Piste |
| --- | --- |
| `miara-api` redémarre en boucle | `journalctl -u miara-api -n 50`. Le plus souvent : `/etc/miara/.env` incomplet, ou `.venv` absent (lancer `deploy.sh`). |
| `/health` répond 503 | La réponse nomme le composant fautif (`database`, `broker`, `redis`). Vérifier `systemctl status postgresql rabbitmq-server redis-server`. |
| 502 sur `/api/` | `miara-api` est arrêté, ou écoute ailleurs que sur 8010. `ss -lntp | grep 8010`. |
| 502 sur `/` | `miara-web` arrêté, ou build manquant : `ls /srv/miara/frontend/.next`. |
| Le flux SSE arrive d'un bloc à la fin | Une couche met en tampon. Vérifier que `proxy_buffering off` est bien dans le vhost actif (`nginx -T | grep -A5 stream`) et qu'aucun proxy/CDN ne s'intercale. |
| 413 au dépôt de CV | `client_max_body_size` du vhost (200 Mo) ou bornes applicatives `HR_MAX_UPLOAD_FILES` / `HR_MAX_FILE_MB`. |
| `permission denied` sur les CV | `/var/lib/miara/storage` doit appartenir à `miara` en 700, et `HR_STORAGE_DIR` pointer dessus. |
| Les tâches RH restent en attente | `miara-worker-heavy` arrêté, ou mauvais vhost RabbitMQ dans `RABBITMQ_URL`. `sudo rabbitmqctl list_queues -p miara`. |
| Une requête ne voit aucune donnée | Comportement attendu si `app.current_org` n'est pas positionné : c'est le RLS qui fait son travail (ADR-002), pas une panne. |
| `alembic` échoue en `permission denied` | Les migrations doivent passer par `miara_admin` : vérifier `DATABASE_URL_ADMIN`. |
| Le certificat a expiré | `systemctl status certbot.timer`, puis `sudo certbot renew --force-renewal` et `sudo systemctl reload nginx`. |
| Plus d'accès SSH après `ufw` | Console de secours de l'hébergeur : `ufw allow 22/tcp`. Le script autorise le 22 avant d'activer le pare-feu, précisément pour éviter ça. |

---

## 9. Ce qui a été vérifié, et comment

Vérifications réellement exécutées sur la machine de développement
(Ubuntu 26.04, PostgreSQL 18.6, nginx 1.28, systemd), sans jamais toucher aux
services en place :

| Quoi | Comment | Résultat |
| --- | --- | --- |
| Scripts shell | `bash -n` et `shellcheck -S style` sur les quatre scripts + le hook certbot | aucun avertissement |
| vhost de production | `nginx -t` sur une instance isolée, domaine factice `miara.test`, certificat auto-signé | syntaxe valide |
| vhost de bootstrap | idem | syntaxe valide |
| Proxy `/` | instance nginx de test en loopback (18443) devant le vrai serveur Next du poste (3010) | 307 vers `/login`, en-têtes de sécurité présents, `server: nginx` |
| Redirection HTTP | `curl http://…:18080/x` | 301 vers `https://` |
| Flux SSE | faux backend émettant un évènement par seconde sur `/api/v1/…/stream`, lu au travers de nginx | chaque évènement reçu 15 ms après son émission, 1 s d'écart : aucun tampon |
| `client_max_body_size` | POST de 210 Mo puis de 150 Mo | 413 au-dessus de 200 Mo, corps accepté en dessous |
| gzip | `Accept-Encoding: gzip` sur une page du front | `content-encoding: gzip` (et rien sur le flux SSE) |
| Blocage de la doc | `curl /docs`, `/redoc`, `/openapi.json` | 404 |
| Units systemd | `systemd-analyze verify` sur les quatre unités | aucune erreur hors binaires absents de ce poste |
| Démarrage réel de l'API | unité dérivée de `miara-api.service` (seuls chemins, compte, port et `EnvironmentFile` changés), chargée depuis `/run/systemd/system` | démarre avec tout le durcissement, `${API_WORKERS}=2` donne bien deux processus |
| Redémarrage automatique | `systemctl kill --signal=SIGKILL` sur cette unité, mesure jusqu'au retour de `/health` en 200 | 8,6 s et 8,8 s sur deux essais (11,7 s avec l'ancien `RestartSec=5`, d'où son passage à 2) |
| `EnvironmentFile` | `systemd-run -p EnvironmentFile=deploy/.env.example` | systemd relit correctement le fichier, guillemets compris |
| sudoers | `visudo -cf` | valide **après correction** : les jokers `miara-*` étaient refusés |
| logrotate | `logrotate -v --debug` sur une copie en 0644 root | accepté (le seul refus venait du groupe `miara`, absent de ce poste) |
| Réglages journald | comparaison des clés avec `/etc/systemd/journald.conf` | les sept directives existent |
| Sauvegarde | `backup_db.sh` lancé pour de vrai sur la base de dev | corrigé puis OK : dump de 286 ko, sommaire `pg_restore` relu |
| Rotation | dumps antidatés de 20 et 3 jours + un `.partial` orphelin, puis nouvelle sauvegarde | seul le dump de 20 jours et l'orphelin sont supprimés |
| Restauration | `restore_db.sh --dry-run`, puis `--create --into miara_restore_test` | 16 tables, 14 politiques RLS, aucune table en RLS non forcé |
| Fidélité des données | comptes de lignes comparés entre la base source et la base restaurée | identiques (4 organisations, 5 utilisateurs, 177 notations, 778 appels LLM) |
| Isolation après restauration | `SET ROLE miara_app` sans `app.current_org` sur la base restaurée | 0 ligne visible sur `llm_calls` et `candidate_scores`, contre 778 et 177 en superutilisateur |
| Garde-fous de `deploy.sh` | `--help`, argument inconnu, `--ref` sans valeur, `.env` illisible, mauvais compte | chaque cas refusé avec le bon message |

### Ce qui reste invérifiable sans un VPS neuf et un domaine

1. **`setup_vps.sh` de bout en bout** : noms de paquets, dépôt PGDG,
   installation de `uv` dans `/usr/local/bin`, `ufw`. Le script n'a jamais été
   exécuté : il installe des services système et aurait cassé le poste de
   développement. Seules sa syntaxe et les fichiers qu'il installe sont
   vérifiés.
2. **Le certificat Let's Encrypt** : émission, DNS, challenge HTTP-01,
   renouvellement. Rien de tout cela ne peut être simulé ici. Premier test à
   faire sur le VPS : `sudo certbot renew --dry-run`.
3. **Les workers Celery sous systemd** : leurs unités passent
   `systemd-analyze verify`, mais les démarrer ici aurait consommé les files
   RabbitMQ de développement. Vérifier `journalctl -u miara-worker-heavy` au
   premier déploiement.
4. **`deploy.sh` de bout en bout** : `git pull`, `uv sync`, `alembic upgrade
   head`, `npm ci && npm run build` et le redémarrage des quatre services
   supposent `/srv/miara` et les units installées. Les seuls garde-fous testés
   sont ceux listés plus haut.
5. **La durée d'indisponibilité pendant un déploiement** (critère « moins de
   5 s ») : elle dépend du temps de démarrage réel des quatre services sur le
   VPS. Mesurée ici sur l'API seule, hors nginx : ~6 s d'import applicatif
   avant la première réponse. Le critère est donc à considérer comme **non
   tenu en l'état** : un déploiement coupe le service quelques secondes. Le
   tenir vraiment demanderait deux répertoires de version et un basculement de
   symlink (voir §3).
6. **PostgreSQL 16 contre 18** : `setup_vps.sh` installe la 16 (demande de la
   carte, dépôt PGDG au besoin) alors que le développement tourne sur la 18.
   Tout ce qui a été vérifié ici l'a donc été sur la 18. Aligner les deux
   (`PG_VERSION=18` au provisionnement, ou rétrograder le poste) avant la
   campagne de charge, sinon les mesures ne porteront pas sur le même moteur.
7. **La suppression de l'utilisateur RabbitMQ `guest`** : si un `RABBITMQ_URL`
   traîne avec `guest`, les workers ne se connecteront plus. Cohérence à
   vérifier avec `/etc/miara/.env`.
