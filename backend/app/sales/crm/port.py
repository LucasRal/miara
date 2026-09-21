"""Port CRM abstrait (ADR-005) : le cœur du module sales ne connaît que cette
interface. Implémentations : `SalesforceClient` (réel) et `FakeCRM` (tests,
mode démo). Ouverture multi-CRM (mémoire, chap. 9) : un futur HubSpotClient
implémente ce même Protocol sans toucher aux agents.
"""

from typing import Any, Protocol, runtime_checkable


class CRMError(Exception):
    """Erreur CRM générique (réseau, 5xx, réponse inattendue)."""


class CRMAuthError(CRMError):
    """Authentification impossible : pas d'intégration, jetons invalides ou
    refresh refusé. L'utilisateur doit (re)connecter son Salesforce."""


class CRMRateLimited(CRMError):
    """Quota d'API du CRM atteint : réessayer plus tard."""


@runtime_checkable
class CRMPort(Protocol):
    """Contrat minimal d'accès CRM. Les données sont des dicts « bruts » du
    fournisseur ; l'interprétation métier appartient aux outils d'agent."""

    async def query(self, soql: str) -> list[dict[str, Any]]:
        """Exécute une requête SOQL et retourne toutes les lignes (pagination
        suivie par l'implémentation)."""
        ...

    async def get(self, object: str, id: str) -> dict[str, Any]:
        """Retourne un enregistrement par type d'objet et id."""
        ...

    async def create(self, object: str, data: dict[str, Any]) -> str:
        """Crée un enregistrement et retourne son id."""
        ...

    async def update(self, object: str, id: str, data: dict[str, Any]) -> None:
        """Met à jour partiellement un enregistrement."""
        ...

    async def aclose(self) -> None:
        """Libère les ressources réseau (no-op pour les implémentations en mémoire)."""
        ...
