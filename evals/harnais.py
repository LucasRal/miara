"""Socle du harnais : organisation d'évaluation, passerelle tracée, rapport.

Trois choix structurants, qui valent pour les quatre suites.

1. **Le harnais appelle le code de production, il ne le réimplémente pas.**
   Chaque suite passe par les fonctions du dépôt (`app.hr.pipeline`,
   `app.core.agents.runtime`) avec leurs prompts versionnés et leurs alias. Une
   copie du montage des prompts dans le harnais mesurerait le harnais, pas le
   produit, et un changement de prompt redeviendrait une régression invisible.

2. **Une organisation dédiée, avec un identifiant fixe.** Les campagnes
   d'évaluation vivent dans la même base que le reste, isolées par RLS comme
   n'importe quel locataire. L'identifiant est constant d'un rejeu à l'autre :
   les lignes `llm_calls` d'une évaluation se retrouvent par une seule
   condition, et aucune donnée d'évaluation ne se mélange à une organisation
   réelle.

3. **Tous les appels sont marqués `eval.*`.** La passerelle du harnais
   préfixe le nom d'agent avant l'écriture dans `llm_calls`
   (`hr.score` -> `eval.hr.score`). Le coût d'une campagne d'évaluation se lit
   donc d'une requête, et il ne pollue pas les statistiques d'usage montrées
   aux clients.
"""

from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.models import Membership, MembershipRole, Organization, User
from app.config import settings
from app.core.crypto import encrypt_credentials
from app.core.llm import CallContext, LLMGateway, LLMResult
from app.core.models import Integration
from evals import DONNEES, RAPPORTS

# Organisation d'évaluation : identifiant FIXE, jamais tiré au hasard.
ORG_EVAL = uuid.UUID("e7a10000-0000-4000-8000-000000000001")
USER_EVAL = uuid.UUID("e7a10000-0000-4000-8000-000000000002")
EMAIL_EVAL = "harnais@evaluation.invalid"

# Préfixe des noms d'agent dans `llm_calls` pendant une évaluation.
PREFIXE = "eval."


class PasserelleEval(LLMGateway):
    """La passerelle de production, avec le nom d'agent préfixé `eval.`.

    Rien d'autre ne change : même routeur, mêmes replis, même journalisation.
    Le préfixe est posé sur le contexte d'appel, pas sur l'alias : c'est bien
    le MÊME alias, donc le même modèle, qui est mesuré.
    """

    async def complete(
        self,
        alias: str,
        messages: Any,
        *,
        ctx: CallContext,
        tools: list[dict[str, Any]] | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> LLMResult:
        if not ctx.agent.startswith(PREFIXE):
            ctx = replace(ctx, agent=f"{PREFIXE}{ctx.agent}")
        return await super().complete(
            alias, messages, ctx=ctx, tools=tools, response_model=response_model
        )


def charger_config_llm(surcharges: dict[str, str] | None = None) -> dict[str, Any]:
    """Config LiteLLM du dépôt, éventuellement surchargée alias par alias.

    `--alias-override hr.score=<modele>` sert à comparer deux modèles sur le
    même jeu. La surcharge remplace le modèle primaire ET retire les replis :
    sinon un repli silencieux ferait passer pour « mesuré » un modèle qui n'a
    jamais répondu. Le nom du modèle vient de la ligne de commande, jamais du
    code (ADR-011) : le dépôt continue de ne connaître que des alias.
    """
    chemin = Path(settings.LLM_CONFIG_PATH) if settings.LLM_CONFIG_PATH else None
    if chemin is None:
        chemin = Path(__file__).resolve().parents[1] / "backend" / "config" / "llm.yaml"
    config: dict[str, Any] = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    for alias, modele in (surcharges or {}).items():
        if alias not in config["aliases"]:
            raise SystemExit(f"Alias inconnu dans la surcharge : {alias!r} (voir config/llm.yaml)")
        config["aliases"][alias] = {"primary": modele}
    return config


def passerelle(surcharges: dict[str, str] | None = None) -> PasserelleEval:
    return PasserelleEval(config=charger_config_llm(surcharges))


def _moteur_admin() -> Any:
    """Connexion propriétaire : créer une organisation échappe au RLS."""
    return create_async_engine(settings.DATABASE_URL_ADMIN)


async def preparer_organisation() -> None:
    """Crée (une fois pour toutes) l'organisation d'évaluation et son CRM factice.

    Idempotent : un rejeu ne duplique rien. L'intégration `mode=fake` est ce
    qui fait renvoyer un `FakeCRM` par `get_crm`, sans toucher au code de
    production ni à une vraie connexion Salesforce.
    """
    moteur = _moteur_admin()
    sessions = async_sessionmaker(moteur, expire_on_commit=False)
    try:
        async with sessions() as session, session.begin():
            if await session.get(Organization, ORG_EVAL) is None:
                session.add(
                    Organization(id=ORG_EVAL, name="Harnais d'évaluation", slug="harnais-eval")
                )
            if await session.get(User, USER_EVAL) is None:
                session.add(
                    User(
                        id=USER_EVAL,
                        email=EMAIL_EVAL,
                        # Compte de service : aucun mot de passe ne peut
                        # produire ce condensat, donc aucune connexion possible.
                        password_hash="!",
                        full_name="Harnais d'évaluation",
                    )
                )
            await session.flush()
            membre = await session.get(Membership, (USER_EVAL, ORG_EVAL))
            if membre is None:
                session.add(
                    Membership(
                        user_id=USER_EVAL, organization_id=ORG_EVAL, role=MembershipRole.owner
                    )
                )
            integration = (
                await session.execute(
                    select(Integration).where(
                        Integration.organization_id == ORG_EVAL,
                        Integration.provider == "salesforce",
                    )
                )
            ).scalar_one_or_none()
            if integration is None:
                session.add(
                    Integration(
                        organization_id=ORG_EVAL,
                        provider="salesforce",
                        encrypted_credentials=encrypt_credentials({"mode": "fake"}),
                        instance_url=None,
                    )
                )
    finally:
        await moteur.dispose()


@dataclass
class Execution:
    """Ce qui identifie une exécution du harnais, repris dans le rapport."""

    date: str
    sha: str
    suites: list[str]
    limite: int | None
    live: bool
    surcharges: dict[str, str]

    @property
    def nom_de_fichier(self) -> str:
        horodatage = self.date.replace(":", "").replace("-", "").replace(".", "")[:15]
        return f"{horodatage}_{self.sha}.json"


def sha_court() -> str:
    """Empreinte du code évalué. `inconnu` hors dépôt git, `<sha>-sale` si le
    répertoire de travail contient des modifications non committées : un
    rapport doit dire s'il porte sur un état reproductible."""
    racine = Path(__file__).resolve().parents[1]
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=racine,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        propre = subprocess.run(
            ["git", "status", "--porcelain"], cwd=racine, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "inconnu"
    return sha if not propre else f"{sha}-sale"


def nouvelle_execution(
    suites: list[str], limite: int | None, live: bool, surcharges: dict[str, str]
) -> Execution:
    return Execution(
        date=datetime.now(UTC).isoformat(timespec="seconds"),
        sha=sha_court(),
        suites=suites,
        limite=limite,
        live=live,
        surcharges=surcharges,
    )


def chemin_rapport(execution: Execution, destination: Path | None) -> Path:
    chemin = destination or (RAPPORTS / execution.nom_de_fichier)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    return chemin


def dossier_donnees(*parties: str) -> Path:
    return DONNEES.joinpath(*parties)
