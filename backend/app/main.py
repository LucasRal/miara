"""FastAPI application entrypoint.

Wires configuration, CORS, and the versioned API routers. Business logic
never lives here — routers delegate to services (see app/services/).
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import items

# Root logger config so `logging.getLogger(__name__)` calls inside
# routers/services actually emit. Uvicorn only wires its own loggers.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.API_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All feature routers mount under /api/v1. Add new routers here.
api_prefix = f"/api/{settings.API_VERSION}"
app.include_router(items.router, prefix=api_prefix)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Unversioned liveness probe for load balancers / uptime checks."""
    return {"status": "healthy"}
