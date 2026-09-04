"""Dépendances FastAPI : contexte de requête `(user_id, org_id, role)` vérifié.

Chaîne de confiance (contrainte 2 de l'architecture) :
1. JWT signé (cookie httpOnly `access`, ou en-tête Bearer pour les outils) ;
2. la membership est RELUE en base à chaque requête — un rôle révoqué ou une
   membership supprimée invalident le token immédiatement (le claim `role`
   du JWT n'est jamais utilisé pour autoriser) ;
3. la session SQL de la requête est scellée par `set_config` sur
   `app.current_org` + `app.current_user` : le RLS s'applique à tout ce que
   fait l'endpoint. `org_id` ne vient JAMAIS d'un argument client ou LLM.
"""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Membership, MembershipRole
from app.auth.security import decode_access_token
from app.core.tenant import tenant_session

_CREDENTIALS_401 = HTTPException(status_code=401, detail="Authentification requise")


@dataclass(frozen=True)
class TokenClaims:
    """Claims du JWT vérifié (signature + expiration). Pas encore d'accès BDD."""

    user_id: uuid.UUID
    org_id: uuid.UUID | None


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.removeprefix("Bearer ")
    return request.cookies.get("access")


async def get_token_claims(request: Request) -> TokenClaims:
    token = _extract_token(request)
    if token is None:
        raise _CREDENTIALS_401
    claims = decode_access_token(token)
    if claims is None:
        raise _CREDENTIALS_401
    org = claims.get("org")
    return TokenClaims(
        user_id=uuid.UUID(claims["sub"]),
        org_id=uuid.UUID(org) if org else None,
    )


Claims = Annotated[TokenClaims, Depends(get_token_claims)]


@dataclass
class RequestContext:
    """Contexte locataire complet + session SQL déjà scellée par le RLS."""

    user_id: uuid.UUID
    org_id: uuid.UUID
    role: MembershipRole
    session: AsyncSession


async def get_context(claims: Claims) -> AsyncIterator[RequestContext]:
    if claims.org_id is None:
        raise HTTPException(status_code=401, detail="Aucune organisation active")
    async with tenant_session(claims.org_id, claims.user_id) as session:
        membership = await session.get(Membership, (claims.user_id, claims.org_id))
        if membership is None:  # révoquée depuis l'émission du token
            raise HTTPException(status_code=401, detail="Accès à l'organisation révoqué")
        yield RequestContext(
            user_id=claims.user_id,
            org_id=claims.org_id,
            role=membership.role,
            session=session,
        )


Context = Annotated[RequestContext, Depends(get_context)]


def require_role(*roles: str) -> Callable[..., Awaitable[RequestContext]]:
    """Garde d'autorisation : 403 si le rôle (relu en base) n'est pas permis."""

    async def dependency(ctx: Context) -> RequestContext:
        if ctx.role.value not in roles:
            raise HTTPException(status_code=403, detail="Rôle insuffisant")
        return ctx

    return dependency
