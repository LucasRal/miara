# Figures de la partie 2

Deux familles de figures, toutes deux regenerables par une commande. Aucune
figure n'est dessinee a la main dans un editeur graphique.

## 1. Schemas (20 fichiers, `out/*.pdf`)

```
./thesis/figures/render.sh
```

Le script fait deux choses, dans cet ordre.

**Il engendre d'abord les sources derivees du depot** (8 figures). Ces
diagrammes ne sont pas ecrits a la main : ils sont produits par introspection
du code, de sorte qu'une divergence entre le memoire et le depot se traduise
par une figure qui change ou par un script qui echoue.

| source engendree            | script                     | derive de                                  |
|-----------------------------|----------------------------|--------------------------------------------|
| `schema-socle.mmd`          | `gen/schema_bdd.py socle`        | metadonnees SQLAlchemy (`Base.metadata`) |
| `schema-agents.mmd`         | `gen/schema_bdd.py agents`       | idem                                     |
| `schema-exploitation.mmd`   | `gen/schema_bdd.py exploitation` | idem                                     |
| `schema-rh.mmd`             | `gen/schema_bdd.py rh`           | idem                                     |
| `alias-modeles.mmd`         | `gen/alias_modeles.py`           | `backend/config/llm.yaml`                |
| `catalogue-outils.mmd`      | `gen/catalogue_outils.py`        | objets `Tool` declares dans `app/sales/` |
| `dependances-modules.mmd`   | `gen/dependances_modules.py`     | AST des imports de `backend/app/**/*.py` |
| `versions-prompts.mmd`      | `gen/versions_prompts.py`        | arborescence de `prompts/`               |

Les types de colonnes sont compiles pour le dialecte PostgreSQL : ce sont donc
les types que les migrations creent. Deux generateurs echouent volontairement
plutot que de produire une figure fausse : `dependances_modules.py` signale une
violation du sens des dependances (`core` important un module metier), et
`catalogue_outils.py` sort en erreur si un schema d'argument d'outil expose
`org_id`, `organization_id`, `access_token`, `instance_url` ou `credentials`.

**Il compile ensuite les 20 sources** de `src/*.mmd` en PDF vectoriel avec
`mermaid-cli`. Les echecs sont collectes et le script sort en erreur a la fin
plutot qu'au premier probleme.

Prerequis, installes une fois :

```
cd thesis/figures && PUPPETEER_SKIP_DOWNLOAD=1 npm install
```

`mermaid-cli` a besoin d'un Chromium. Le script reutilise celui du cache
Playwright deja present sur la machine ; il le cherche automatiquement, et
`PUPPETEER_EXECUTABLE_PATH` permet de le forcer. Aucun telechargement de
navigateur n'est declenche.

## 2. Captures d'ecran (`captures/out/*.png`)

```
cd thesis/figures
CAPTURES_PASSWORD=... node captures/capturer.mjs
```

Prealable, idempotent, a rejouer seulement si le compte de capture n'existe pas
encore dans l'organisation visee :

```
cd backend && CAPTURES_PASSWORD=... uv run python ../thesis/figures/captures/preparer.py
```

L'application doit tourner sur ses **ports fixes** : frontend 3010, backend
8010, en developpement comme en production (voir `CLAUDE.md`). Le mot de passe
du compte de capture est lu dans `CAPTURES_PASSWORD` et n'est jamais ecrit dans
le depot.

Chaque campagne ecrit `captures/out/manifeste.json` avec la date ISO, la
revision courte du depot et l'URL de base. Les legendes du memoire reprennent
cette date : une capture non datee ne doit pas entrer dans le document.

`CAPTURES_PAGES` permet de restreindre ou de rediriger la liste des ecrans, par
exemple lorsque les identifiants d'une campagne de presélection changent.

## Construction du PDF de la partie

```
make thesis PARTIE=partie2
```

La chaine (`thesis/build.sh`) est celle de la partie 1, reutilisee sans
modification ; les chemins `figures/out/...` des figures se resolvent par le
`--resource-path` qu'elle passe deja a pandoc.
