# Miara - cibles de développement. Ports fixes : API 8010, web 3010.

.PHONY: api worker worker-heavy worker-light web migrate test types gen-data bench bench-sales eval-coach eval eval-verifier eval-compare lint thesis slides

api: ## API FastAPI (uvicorn) sur http://localhost:8010
	cd backend && uv run uvicorn app.main:app --reload --port 8010

# Concurrences par défaut identiques à `deploy/.env.example` : le
# développement doit mesurer la machine que le VPS fait tourner, pas une autre.
WORKER_HEAVY_CONCURRENCY ?= 4
WORKER_LIGHT_CONCURRENCY ?= 2

worker: ## Les deux workers Celery, un par file, comme le VPS (Ctrl-C arrête les deux)
	cd backend && ( \
	  uv run celery -A app.core.celery_app worker -Q heavy \
	    -c $(WORKER_HEAVY_CONCURRENCY) -n heavy@%h --loglevel info & \
	  uv run celery -A app.core.celery_app worker -Q light \
	    -c $(WORKER_LIGHT_CONCURRENCY) -n light@%h --loglevel info & \
	  trap 'kill 0' INT TERM; wait )

worker-heavy: ## Worker de la file heavy seule (extraction, notation)
	cd backend && uv run celery -A app.core.celery_app worker -Q heavy \
	  -c $(WORKER_HEAVY_CONCURRENCY) -n heavy@%h --loglevel info

worker-light: ## Worker de la file light seule (sync CRM, notifications)
	cd backend && uv run celery -A app.core.celery_app worker -Q light \
	  -c $(WORKER_LIGHT_CONCURRENCY) -n light@%h --loglevel info

web: ## Frontend Next.js sur http://localhost:3010
	cd frontend && npm run dev

migrate: ## Applique les migrations Alembic
	cd backend && uv run alembic upgrade head

test: ## Tests backend (pytest) puis frontend (node --test)
	cd backend && uv run pytest
	cd frontend && npm test

types: ## Régénère les types TS du frontend depuis l'OpenAPI FastAPI
	cd backend && uv run python -m scripts.dump_openapi > openapi.json
	cd frontend && npm run types
	rm -f backend/openapi.json

gen-data: ## Régénère le jeu doré evals/data (graine fixe, sortie identique)
	cd backend && uv run python -m scripts.gen_cvs

# Comme le harnais : depuis backend/, avec la racine du dépôt sur le chemin
# d'import. La campagne démarre ses propres workers Celery — arrêter `make
# worker` avant, sinon elle refuse de partir.
bench: ## Campagne de charge, chap. 8 (ARGS="--budget-usd 20 --point hr-50:4:3")
	cd backend && PYTHONPATH=.. uv run python -m scripts.bench $(ARGS)

bench-sales: ## Latence de l'agent commercial sur le jeu doré (ORG=<uuid>)
	cd backend && uv run python -m scripts.bench_sales_assistant --org $(ORG)

eval-coach: ## Accord coach/annotation humaine + test d'injection (ORG=<uuid>)
	cd backend && uv run python -m scripts.eval_coach --org $(ORG)

# Le harnais vit à la racine (evals/) mais importe app/ : il tourne donc depuis
# backend/, avec la racine du dépôt sur le chemin d'import.
eval: ## Harnais d'évaluation complet (ARGS="--suite hr --limit 5")
	cd backend && PYTHONPATH=.. uv run python -m evals.run executer $(ARGS)

eval-verifier: ## Re-vérifie un rapport archivé contre les seuils (RAPPORT=<fichier>)
	cd backend && PYTHONPATH=.. uv run python -m evals.run verifier $(RAPPORT) $(ARGS)

eval-relire: ## Dépouille la feuille de relecture du juge (RAPPORT=<fichier>)
	cd backend && PYTHONPATH=.. uv run python -m evals.run relire $(RAPPORT)

eval-compare: ## Écarts entre deux rapports (AVANT=<a.json> APRES=<b.json>)
	cd backend && PYTHONPATH=.. uv run python ../evals/compare.py $(AVANT) $(APRES)

lint: ## Ruff + mypy (backend et harnais), ESLint (frontend)
	cd backend && uv run ruff check . ../evals && uv run mypy
	cd frontend && npm run lint

thesis: ## Compile le mémoire en PDF (PARTIE=partie1 par défaut) -> thesis/build/
	./thesis/build.sh $(or $(PARTIE),partie1)

slides: ## Compile les diapositives de soutenance -> thesis/build/diapositives.pdf
	./thesis/soutenance/build-slides.sh
