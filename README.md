# thesis

Full-stack monorepo: a **Next.js** frontend and a **FastAPI** backend, deployed
independently and communicating over REST.

```
thesis/
├── frontend/   # Next.js (App Router, TypeScript, Tailwind v4)
└── backend/    # FastAPI (pydantic-settings, routers/schemas/services)
```

## Architecture

- The two services are **independent deployables**. They never import each
  other — the frontend talks to the backend **only** over HTTP.
- All API endpoints live under `/api/v1/...`. A version-less `/health` is the
  liveness probe.
- **Backend layering:** routers (HTTP) → services (logic) → schemas (Pydantic
  contracts). Routers call services; services never import routers.
- **Frontend styling:** every design token (color, font, radius, shadow) lives
  in `frontend/src/app/globals.css`. Components use Tailwind utilities only —
  no hardcoded design values, no inline styles for design-system properties.

## Prerequisites

- Node.js ≥ 20.9
- Python ≥ 3.10

## Run the backend

```bash
cd backend
source venv/bin/activate          # Windows: venv\Scripts\activate
uvicorn app.main:app --reload     # http://localhost:8000  (docs at /docs)
```

Add a dependency: `pip install <lib>` then `pip freeze > requirements.txt`.
On a fresh clone: `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`.

## Run the frontend

```bash
cd frontend
npm install     # first time / fresh clone
npm run dev     # http://localhost:3000
```

## Environment

Copy the examples and fill them in (real files are git-ignored):

- `backend/.env.example`  → `backend/.env`
- `frontend/.env.local.example` → `frontend/.env.local`
