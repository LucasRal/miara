# Miara - cibles de développement. Ports fixes : API 8010, web 3010.

.PHONY: api worker web migrate test bench-sales eval-coach lint

api: ## API FastAPI (uvicorn) sur http://localhost:8010
	cd backend && uv run uvicorn app.main:app --reload --port 8010

worker: ## Worker Celery consommant les files heavy et light
	cd backend && uv run celery -A app.core.celery_app worker -Q heavy,light --loglevel info

web: ## Frontend Next.js sur http://localhost:3010
	cd frontend && npm run dev

migrate: ## Applique les migrations Alembic
	cd backend && uv run alembic upgrade head

test: ## Tests backend (pytest)
	cd backend && uv run pytest

bench-sales: ## Latence de l'agent commercial sur le jeu doré (ORG=<uuid>)
	cd backend && uv run python -m scripts.bench_sales_assistant --org $(ORG)

eval-coach: ## Accord coach/annotation humaine + test d'injection (ORG=<uuid>)
	cd backend && uv run python -m scripts.eval_coach --org $(ORG)

lint: ## Ruff + mypy (backend), ESLint (frontend)
	cd backend && uv run ruff check . && uv run mypy
	cd frontend && npm run lint
