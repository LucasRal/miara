# Miara - cibles de développement. Ports fixes : API 8010, web 3010.

.PHONY: api worker web migrate test lint

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

lint: ## Ruff + mypy (backend), ESLint (frontend)
	cd backend && uv run ruff check . && uv run mypy
	cd frontend && npm run lint
