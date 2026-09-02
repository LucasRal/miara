"""Shared FastAPI dependencies (injected via `Depends(...)`).

Put cross-cutting request concerns here — auth/current-user, DB sessions,
pagination params — so routers stay thin. Kept intentionally minimal in the
scaffold; delete the example once you add real ones.
"""

from dataclasses import dataclass

from fastapi import Query


@dataclass
class Pagination:
    limit: int
    offset: int


def pagination(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Pagination:
    """Reusable list pagination. Usage: `page: Pagination = Depends(pagination)`."""
    return Pagination(limit=limit, offset=offset)
