"""Endpoints auth : register / login / refresh / logout / me / orgs.

Transport des tokens : cookies httpOnly `access` (path /) et `refresh`
(path restreint aux endpoints /auth) — jamais de localStorage (carte auth).
Le front parle au backend en same-origin via le proxy Next (:3010), les
cookies suivent. L'en-tête `Authorization: Bearer` reste accepté pour les
outils (tests, curl).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.auth import service, tokens
from app.auth.deps import Claims, Context, RequestContext, require_role
from app.auth.models import MembershipRole
from app.auth.schemas import (
    InviteIn,
    LoginIn,
    MemberOut,
    MembershipOut,
    MeOut,
    OrgCreateIn,
    OrgOut,
    RegisterIn,
    RoleUpdateIn,
)
from app.auth.security import create_access_token
from app.config import settings

router = APIRouter(tags=["auth"])

_REFRESH_COOKIE_PATH = f"/api/{settings.API_VERSION}/auth"


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    # max_age = durée du refresh : le JWT à l'intérieur expire avant (15 min),
    # le backend fait foi ; le front rafraîchit sur 401.
    max_age = settings.REFRESH_TOKEN_TTL_DAYS * 86400
    response.set_cookie(
        "access",
        access,
        max_age=max_age,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
    )
    response.set_cookie(
        "refresh",
        refresh,
        max_age=max_age,
        path=_REFRESH_COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access", path="/")
    response.delete_cookie("refresh", path=_REFRESH_COOKIE_PATH)


async def _issue_session(
    response: Response,
    user_id: uuid.UUID,
    org_id: uuid.UUID | None,
    role: MembershipRole | None,
) -> None:
    access = create_access_token(user_id, org_id, role.value if role else None)
    refresh = await tokens.issue_refresh_token(user_id, org_id)
    _set_auth_cookies(response, access, refresh)


@router.post("/auth/register", status_code=201)
async def register(data: RegisterIn, response: Response) -> MeOut:
    user = await service.register_user(data)
    await _issue_session(response, user.id, None, None)
    return await service.build_me(user.id, None)


@router.post("/auth/login")
async def login(data: LoginIn, request: Request, response: Response) -> MeOut:
    ip = request.client.host if request.client else "unknown"
    user = await service.authenticate(data.email, data.password, ip)
    membership = await service.default_membership(user.id)
    org_id = membership.organization_id if membership else None
    role = membership.role if membership else None
    await _issue_session(response, user.id, org_id, role)
    return await service.build_me(user.id, org_id)


@router.post("/auth/refresh")
async def refresh(request: Request, response: Response) -> dict[str, str]:
    token = request.cookies.get("refresh")
    record = await tokens.consume_refresh_token(token) if token else None
    if record is None:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="Session expirée ou révoquée")

    user_id = uuid.UUID(str(record["user_id"]))
    org_raw = record.get("org_id")
    org_id = uuid.UUID(str(org_raw)) if org_raw else None
    role: MembershipRole | None = None
    if org_id is not None:
        membership = await service.get_membership(user_id, org_id)
        if membership is None:  # accès révoqué entre-temps : ré-authentification
            _clear_auth_cookies(response)
            raise HTTPException(status_code=401, detail="Accès à l'organisation révoqué")
        role = membership.role
    await _issue_session(response, user_id, org_id, role)
    return {"detail": "ok"}


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, response: Response) -> None:
    token = request.cookies.get("refresh")
    if token:
        await tokens.revoke_refresh_token(token)
    _clear_auth_cookies(response)


@router.get("/me")
async def me(claims: Claims) -> MeOut:
    return await service.build_me(claims.user_id, claims.org_id)


@router.post("/orgs", status_code=201)
async def create_org(data: OrgCreateIn, claims: Claims, response: Response) -> OrgOut:
    org = await service.create_organization(claims.user_id, data)
    # Le contexte actif bascule sur la nouvelle organisation (parcours
    # inscription -> création d'org -> tableau de bord).
    await _issue_session(response, claims.user_id, org.id, MembershipRole.owner)
    return org


@router.post("/orgs/{org_id}/switch")
async def switch_org(org_id: uuid.UUID, claims: Claims, response: Response) -> MeOut:
    membership = await service.get_membership(claims.user_id, org_id)
    if membership is None:
        raise HTTPException(status_code=403, detail="Pas membre de cette organisation")
    await _issue_session(response, claims.user_id, org_id, membership.role)
    return await service.build_me(claims.user_id, org_id)


@router.post("/orgs/{org_id}/invite", status_code=201)
async def invite(
    org_id: uuid.UUID,
    data: InviteIn,
    ctx: Annotated[RequestContext, Depends(require_role("owner", "admin"))],
) -> MembershipOut:
    if org_id != ctx.org_id:
        raise HTTPException(status_code=403, detail="Organisation hors contexte actif")
    return await service.invite_member(ctx.session, org_id, data.email, data.role)


@router.get("/orgs/{org_id}/members")
async def list_members(org_id: uuid.UUID, ctx: Context) -> list[MemberOut]:
    """Membres de l'organisation ACTIVE (page Paramètres).

    Lisible par tout membre ; `org_id` d'URL doit correspondre au contexte —
    c'est le token, pas l'URL, qui décide de l'organisation consultée.
    """
    if org_id != ctx.org_id:
        raise HTTPException(status_code=403, detail="Organisation hors contexte actif")
    return await service.list_members(ctx.session, org_id)


@router.patch("/orgs/{org_id}/members/{user_id}")
async def update_member_role(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    data: RoleUpdateIn,
    ctx: Annotated[RequestContext, Depends(require_role("owner", "admin"))],
) -> MemberOut:
    if org_id != ctx.org_id:
        raise HTTPException(status_code=403, detail="Organisation hors contexte actif")
    return await service.update_member_role(ctx.session, org_id, ctx.user_id, user_id, data.role)


@router.delete("/orgs/{org_id}/members/{user_id}", status_code=204)
async def remove_member(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    ctx: Annotated[RequestContext, Depends(require_role("owner", "admin"))],
) -> None:
    """Retire un membre de l'organisation active.

    Le rôle est relu à chaque requête : le retrait prend effet immédiatement,
    y compris pour une session déjà ouverte.
    """
    if org_id != ctx.org_id:
        raise HTTPException(status_code=403, detail="Organisation hors contexte actif")
    await service.remove_member(ctx.session, org_id, ctx.user_id, user_id)
