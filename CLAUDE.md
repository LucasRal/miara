# CLAUDE.md - Miara (Mémoire M2)

Plateforme SaaS multi-locataire : agents LLM pour équipes commerciales (Salesforce) et RH (présélection de CV).
Pilotage par le tableau Trello « Miara - Mémoire M2 » (id `6a979fb6bd8395594ab39af7`, credentials dans `backend/.trello.env`).
Architecture de référence : cartes [RÉF] du tableau + `docs/adr/`.

## Contraintes non négociables ([RÉF] Architecture macro)

1. **Isolation multi-locataire par RLS** : `organization_id` sur toute table métier ; politiques Row-Level Security PostgreSQL avec `SET LOCAL app.current_org` à chaque requête.
2. **`org_id` et credentials viennent TOUJOURS du contexte de requête**, jamais des arguments produits par le LLM.
3. **Deux files Celery** : `heavy` (extraction, scoring LLM) et `light` (sync CRM, notifications). Toute tâche est idempotente, avec clé `job_id`.
4. **Aucun nom de modèle LLM en dur dans le code** - alias de configuration uniquement (LiteLLM Router).
5. **Prompts = fichiers versionnés dans le dépôt** : `prompts/<agent>/v<N>.md` ; `prompt_version` journalisée à chaque appel.

## Conventions

### Modules backend (`backend/app/`)
- **`auth/`** : utilisateurs, organisations, memberships (rôles owner/admin/sales/hr), JWT émis par FastAPI (pas de NextAuth/Keycloak - ADR-003).
- **`hr/`** : présélection N CV → 1 offre (pipeline Celery, file `heavy` ; notation par CV indépendant - ADR-007).
- **`sales/`** : agent conversationnel + outils Salesforce (OAuth par org, credentials chiffrés, interface `CRMPort` - ADR-005).
- **`core/`** : runtime d'agent (boucle bornée max_steps=6, sans framework), passerelle LLM, outils typés, traçage (`llm_calls`), infra transverse (logging, db, celery, health).
- Sens des dépendances : `auth`/`hr`/`sales` peuvent importer `core` ; `core` n'importe jamais un module métier. Monolithe modulaire, un seul déployable (ADR-001).

### Alias de modèles (ADR-011)
`sales.route` (léger) · `sales.synthesize` (fort) · `hr.extract` (léger, JSON) · `hr.score` (fort, JSON).
Définis dans la config LiteLLM Router avec replis. Changer de fournisseur = changer la config, jamais le code.

### Prompts versionnés (ADR-010)
`prompts/<agent>/v<N>.md` (ex. `prompts/sales_synthesize/v1.md`). Un changement de prompt = un nouveau fichier `v<N+1>.md`, jamais d'écrasement. La version utilisée est journalisée dans `llm_calls`.

## Processus de travail (Trello)

a. Ne travailler QUE sur la carte présente dans « 🎯 À faire ».
b. La déplacer en « 🔨 En cours » au démarrage du travail.
c. Respecter strictement la section « NE PAS » de la carte.
d. Vérifier chaque critère d'acceptation, un par un, avant de considérer la carte finie.
e. À la fin : déplacer la carte en « 🔍 À valider » et y poster un commentaire avec durée réelle, décisions prises, points incertains.
f. Ne JAMAIS déplacer une carte en « ✅ Terminé » - c'est le propriétaire du board qui le fait après validation.

## Secrets

Aucun secret dans le dépôt. Toute valeur sensible (tokens, mots de passe, URLs avec credentials) vit dans un `.env` git-ignoré ; chaque `.env` a son `.env.example` committé, à jour, avec des valeurs factices. Ne jamais committer `backend/.env`, `frontend/.env.local`, `backend/.trello.env`.

## Environnement

- **Ports fixes (dev, build ET tests)** : frontend **3010**, backend **8010**. Le frontend proxifie `/api/*` vers le backend (rewrites Next) - le navigateur ne parle qu'au 3010.
- Test local depuis la machine de l'utilisateur : tunnel SSH `ssh -L 3010:localhost:3010 ubuntu@<vps>`.
- Backend : Python 3.12 géré par **uv** (`uv run ...`, lockfile `uv.lock`). Frontend : Next.js (App Router, TS strict), npm.
- Services natifs Ubuntu (pas de Docker - carte INFRA) : PostgreSQL, RabbitMQ, Redis. `make api` / `make worker` / `make web` / `make migrate` / `make test`.
