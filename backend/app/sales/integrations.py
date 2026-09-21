"""Connexion Salesforce par organisation — OAuth 2.0 Web Server Flow (ADR-005).

Parcours : GET /integrations/salesforce/connect (admin) → consentement
Salesforce → GET /integrations/salesforce/callback → jetons chiffrés dans
`integrations` (RLS) → redirection vers le frontend.

Le `state` est un JWT signé (10 min) portant l'org et l'utilisateur : le
callback — atteint par une redirection du navigateur — n'a pas besoin de
cookie et ne peut pas être rejoué vers une autre organisation. Le
code_verifier PKCE (exigé par les External Client Apps depuis Spring '26)
reste côté serveur (Redis, lié au nonce du state, consommé une seule fois).
Aucun jeton Salesforce n'apparaît dans les réponses, les logs ni les URLs.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from sqlalchemy import select

from app.auth.deps import Context, RequestContext, require_role
from app.config import settings
from app.core.crypto import decrypt_credentials, encrypt_credentials
from app.core.models import Integration
from app.core.tenant import tenant_session
from app.sales.crm import salesforce
from app.sales.crm.port import CRMAuthError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])

_STATE_TTL_MINUTES = 10
_PKCE_PREFIX = "sf:pkce:"
AdminContext = Annotated[RequestContext, Depends(require_role("owner", "admin"))]

_redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)


def _make_state(org_id: uuid.UUID, user_id: uuid.UUID, nonce: str) -> str:
    claims = {
        "type": "sf_state",
        "org": str(org_id),
        "sub": str(user_id),
        "nonce": nonce,
        "exp": datetime.now(UTC) + timedelta(minutes=_STATE_TTL_MINUTES),
    }
    return str(jwt.encode(claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM))


def _read_state(state: str) -> tuple[uuid.UUID, uuid.UUID, str]:
    try:
        claims = jwt.decode(state, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=400, detail="state invalide ou expiré") from exc
    if claims.get("type") != "sf_state":
        raise HTTPException(status_code=400, detail="state invalide ou expiré")
    return uuid.UUID(claims["org"]), uuid.UUID(claims["sub"]), str(claims["nonce"])


@router.get("")
async def list_integrations(ctx: Context) -> list[dict[str, Any]]:
    """Statut des intégrations de l'organisation — jamais les jetons."""
    rows = (await ctx.session.execute(select(Integration))).scalars().all()
    return [
        {"provider": r.provider, "instance_url": r.instance_url, "status": "connected"}
        for r in rows
    ]


@router.get("/salesforce/connect")
async def salesforce_connect(ctx: AdminContext) -> RedirectResponse:
    """Point de départ du flux : redirige vers le consentement Salesforce."""
    if not settings.SF_CLIENT_ID or not settings.SF_CLIENT_SECRET:
        raise HTTPException(
            status_code=503, detail="App OAuth Salesforce non configurée (SF_CLIENT_ID)"
        )
    verifier, challenge = salesforce.make_pkce()
    nonce = uuid.uuid4().hex
    await _redis.set(_PKCE_PREFIX + nonce, verifier, ex=_STATE_TTL_MINUTES * 60)
    url = salesforce.authorize_url(_make_state(ctx.org_id, ctx.user_id, nonce), challenge)
    return RedirectResponse(url, status_code=302)


@router.get("/salesforce/callback")
async def salesforce_callback(
    state: str, code: str | None = None, error: str | None = None
) -> RedirectResponse:
    """Retour de Salesforce : échange le code, chiffre et stocke les jetons."""
    org_id, user_id, nonce = _read_state(state)
    if error or code is None:
        logger.warning("sf_oauth_denied", org_id=str(org_id), error=error)
        return RedirectResponse("/?salesforce=error", status_code=302)

    # GETDEL : le state ne peut servir qu'une fois (et le verifier PKCE ne
    # transite jamais par le navigateur).
    verifier = await _redis.getdel(_PKCE_PREFIX + nonce)
    if verifier is None:
        raise HTTPException(status_code=400, detail="state invalide ou expiré")

    try:
        tokens = await salesforce.exchange_code(code, str(verifier))
    except CRMAuthError:
        return RedirectResponse("/?salesforce=error", status_code=302)

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        # Connected App sans scope refresh_token/offline_access : connexion
        # inutilisable (le jeton d'accès expirerait sans recours).
        logger.warning("sf_oauth_no_refresh_token", org_id=str(org_id))
        return RedirectResponse("/?salesforce=error", status_code=302)

    credentials = {
        "access_token": str(tokens["access_token"]),
        "refresh_token": str(refresh_token),
        "instance_url": str(tokens["instance_url"]),
    }
    encrypted = encrypt_credentials(credentials)

    async with tenant_session(org_id, user_id) as session:
        existing = (
            await session.execute(select(Integration).where(Integration.provider == "salesforce"))
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                Integration(
                    organization_id=org_id,
                    provider="salesforce",
                    encrypted_credentials=encrypted,
                    instance_url=credentials["instance_url"],
                )
            )
        else:  # reconnexion : on remplace les jetons
            existing.encrypted_credentials = encrypted
            existing.instance_url = credentials["instance_url"]

    logger.info("sf_connected", org_id=str(org_id), instance_url=credentials["instance_url"])
    return RedirectResponse("/?salesforce=connected", status_code=302)


@router.post("/salesforce/disconnect")
async def salesforce_disconnect(ctx: AdminContext) -> dict[str, str]:
    """Révoque le refresh token (best-effort) et supprime l'intégration."""
    integration = (
        await ctx.session.execute(select(Integration).where(Integration.provider == "salesforce"))
    ).scalar_one_or_none()
    if integration is None:
        raise HTTPException(status_code=404, detail="Aucune intégration Salesforce")

    credentials = decrypt_credentials(integration.encrypted_credentials)
    if credentials.get("refresh_token"):
        await salesforce.revoke_token(credentials["refresh_token"])
    await ctx.session.delete(integration)
    logger.info("sf_disconnected", org_id=str(ctx.org_id))
    return {"status": "disconnected"}
