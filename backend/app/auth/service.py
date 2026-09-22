"""Logique métier auth : inscription, login, organisations, memberships.

Toutes les lectures/écritures de memberships passent par une session où
`app.current_user` (et `app.current_org` quand il existe) est posé : les
politiques RLS `member_self_access` + `tenant_isolation_memberships` font foi,
même si une requête oubliait un filtre.
"""

import re
import secrets
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import tokens
from app.auth.models import Membership, MembershipRole, Organization, User
from app.auth.schemas import (
    MemberOut,
    MembershipOut,
    MeOut,
    OrgCreateIn,
    OrgOut,
    RegisterIn,
)
from app.auth.security import hash_password, verify_password
from app.core.db import async_session

# Haché d'un mot de passe impossible : égalise le temps de réponse du login
# quand l'email n'existe pas (anti-énumération par chronométrage).
_DUMMY_HASH = hash_password(secrets.token_hex(16))


@asynccontextmanager
async def user_session(user_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    """Session avec `app.current_user` seul : « mes memberships », sans org active."""
    async with async_session() as session:
        async with session.begin():
            await session.execute(
                text("SELECT set_config('app.current_user', :usr, true)"),
                {"usr": str(user_id)},
            )
            yield session


async def register_user(data: RegisterIn) -> User:
    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        full_name=data.full_name,
    )
    try:
        async with async_session() as session, session.begin():
            session.add(user)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Email déjà enregistré") from None
    return user


async def authenticate(email: str, password: str, ip: str) -> User:
    """Vérifie rate limit puis mot de passe. 429 ou 401 en cas d'échec."""
    email = email.lower()
    if not await tokens.register_login_attempt(email, ip):
        raise HTTPException(status_code=429, detail="Trop de tentatives, réessayez plus tard")

    async with async_session() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()

    if user is None:
        verify_password(password, _DUMMY_HASH)
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Identifiants invalides")

    await tokens.reset_login_attempts(email, ip)
    return user


async def get_membership(user_id: uuid.UUID, org_id: uuid.UUID) -> Membership | None:
    async with user_session(user_id) as session:
        return await session.get(Membership, (user_id, org_id))


async def default_membership(user_id: uuid.UUID) -> Membership | None:
    """Organisation active par défaut au login : la première (ordre stable)."""
    async with user_session(user_id) as session:
        rows = (
            await session.execute(
                select(Membership)
                .join(Organization, Membership.organization_id == Organization.id)
                .where(Membership.user_id == user_id)
                .order_by(Organization.slug)
            )
        ).scalars()
        return rows.first()


async def build_me(user_id: uuid.UUID, org_id: uuid.UUID | None) -> MeOut:
    async with user_session(user_id) as session:
        user = await session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="Utilisateur inconnu")
        rows = (
            await session.execute(
                select(Membership, Organization)
                .join(Organization, Membership.organization_id == Organization.id)
                .where(Membership.user_id == user_id)
                .order_by(Organization.slug)
            )
        ).all()
        memberships = [
            MembershipOut(
                organization_id=org.id,
                organization_name=org.name,
                organization_slug=org.slug,
                role=m.role,
            )
            for m, org in rows
        ]
        current = next((m for m in memberships if m.organization_id == org_id), None)
        return MeOut(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            org_id=current.organization_id if current else None,
            role=current.role if current else None,
            memberships=memberships,
        )


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "org"


async def create_organization(user_id: uuid.UUID, data: OrgCreateIn) -> OrgOut:
    """Crée l'organisation et la membership `owner` du créateur (même transaction).

    L'insertion de sa propre membership est permise par la politique
    `member_self_access` (WITH CHECK implicite) — aucune org active requise.
    """
    slugs = [data.slug] if data.slug else [_slugify(data.name)]
    if data.slug is None:
        # Repli anti-collision uniquement pour les slugs générés.
        slugs.append(f"{slugs[0]}-{secrets.token_hex(3)}")

    for candidate in slugs:
        org = Organization(name=data.name, slug=candidate)
        try:
            async with user_session(user_id) as session:
                session.add(org)
                await session.flush()
                session.add(
                    Membership(
                        user_id=user_id,
                        organization_id=org.id,
                        role=MembershipRole.owner,
                    )
                )
            return OrgOut(id=org.id, name=org.name, slug=org.slug)
        except IntegrityError:
            continue
    raise HTTPException(status_code=409, detail="Slug d'organisation déjà pris")


async def invite_member(
    session: AsyncSession, org_id: uuid.UUID, email: str, role: MembershipRole
) -> MembershipOut:
    """Ajoute un utilisateur EXISTANT à l'organisation courante.

    `session` vient du contexte de requête (RLS actif) : le WITH CHECK de
    `tenant_isolation_memberships` interdit d'insérer pour une autre org.
    Pas d'envoi d'email dans ce périmètre (voir commentaire de carte).
    """
    user = (
        await session.execute(select(User).where(User.email == email.lower()))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Aucun utilisateur avec cet email")
    org = await session.get(Organization, org_id)
    if org is None:  # défensif : l'org du contexte existe forcément
        raise HTTPException(status_code=404, detail="Organisation inconnue")

    session.add(Membership(user_id=user.id, organization_id=org_id, role=role))
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Déjà membre de cette organisation") from None
    return MembershipOut(
        organization_id=org_id,
        organization_name=org.name,
        organization_slug=org.slug,
        role=role,
    )


async def list_members(session: AsyncSession, org_id: uuid.UUID) -> list[MemberOut]:
    """Membres de l'organisation courante, triés par nom.

    `session` vient du contexte de requête : `tenant_isolation_memberships`
    borne déjà la lecture à l'org active, la jointure ne fait que rapatrier
    l'identité (les users ne sont pas tenant-scopés).
    """
    rows = (
        await session.execute(
            select(User.id, User.email, User.full_name, Membership.role)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.organization_id == org_id)
            .order_by(User.full_name)
        )
    ).all()
    return [
        MemberOut(user_id=r.id, email=r.email, full_name=r.full_name, role=r.role) for r in rows
    ]


async def update_member_role(
    session: AsyncSession,
    org_id: uuid.UUID,
    actor_id: uuid.UUID,
    target_id: uuid.UUID,
    role: MembershipRole,
) -> MemberOut:
    """Change le rôle d'un membre. Deux garde-fous anti-impasse.

    1. On ne modifie pas son propre rôle (un owner ne peut pas se rétrograder
       et perdre l'accès à cet écran).
    2. L'organisation garde au moins un owner.
    """
    if actor_id == target_id:
        raise HTTPException(status_code=409, detail="Impossible de modifier son propre rôle")

    membership = await session.get(Membership, (target_id, org_id))
    if membership is None:
        raise HTTPException(status_code=404, detail="Membre inconnu")

    if membership.role is MembershipRole.owner and role is not MembershipRole.owner:
        owners = (
            await session.execute(
                select(func.count())
                .select_from(Membership)
                .where(
                    Membership.organization_id == org_id,
                    Membership.role == MembershipRole.owner,
                )
            )
        ).scalar_one()
        if owners <= 1:
            raise HTTPException(
                status_code=409, detail="L'organisation doit garder au moins un owner"
            )

    membership.role = role
    await session.flush()
    user = await session.get(User, target_id)
    assert user is not None  # FK memberships.user_id
    return MemberOut(user_id=user.id, email=user.email, full_name=user.full_name, role=role)


async def remove_member(
    session: AsyncSession,
    org_id: uuid.UUID,
    actor_id: uuid.UUID,
    target_id: uuid.UUID,
) -> None:
    """Retire un membre de l'organisation. Mêmes garde-fous que le changement de rôle.

    Retirer quelqu'un qui quitte l'entreprise est la première opération
    d'administration ; se retirer soi-même, ou retirer le dernier owner, sont
    deux façons de rendre l'organisation ingérable.
    """
    if actor_id == target_id:
        raise HTTPException(status_code=409, detail="Impossible de se retirer soi-même")

    membership = await session.get(Membership, (target_id, org_id))
    if membership is None:
        raise HTTPException(status_code=404, detail="Membre inconnu")

    if membership.role is MembershipRole.owner:
        owners = (
            await session.execute(
                select(func.count())
                .select_from(Membership)
                .where(
                    Membership.organization_id == org_id,
                    Membership.role == MembershipRole.owner,
                )
            )
        ).scalar_one()
        if owners <= 1:
            raise HTTPException(
                status_code=409, detail="L'organisation doit garder au moins un owner"
            )

    await session.delete(membership)
    await session.flush()
