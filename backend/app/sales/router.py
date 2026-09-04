"""Router du module sales — squelette.

Seul endpoint pour l'instant : `GET /sales/ping`, protégé par la garde de
rôle (owner/admin/sales). Il matérialise le contrat d'accès du module ; les
vrais endpoints arrivent avec les cartes [SALES].
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.deps import RequestContext, require_role

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("/ping")
async def sales_ping(
    ctx: Annotated[RequestContext, Depends(require_role("owner", "admin", "sales"))],
) -> dict[str, str]:
    return {"module": "sales", "organization_id": str(ctx.org_id), "role": ctx.role.value}
