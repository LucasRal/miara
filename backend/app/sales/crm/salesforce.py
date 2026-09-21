"""Client Salesforce : le SEUL fichier qui parle à l'API Salesforce (ADR-005).

Deux responsabilités :
- OAuth 2.0 Web Server Flow : URL d'autorisation, échange du code, refresh,
  révocation (endpoints `/services/oauth2/*` du login server) ;
- `SalesforceClient` (CRMPort) : REST `/services/data/v60.0`, Bearer, et sur
  401 : refresh du jeton puis rejeu de la requête UNE fois.

Les jetons ne sont JAMAIS journalisés — logs de métadonnées uniquement.
"""

import asyncio
import base64
import hashlib
import secrets
import urllib.parse
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import structlog

from app.config import settings
from app.sales.crm.port import CRMAuthError, CRMError, CRMRateLimited

logger = structlog.get_logger(__name__)

API_VERSION = "v60.0"
_TIMEOUT = 15.0


# --- OAuth 2.0 Web Server Flow -------------------------------------------


def make_pkce() -> tuple[str, str]:
    """Paire PKCE (RFC 7636) : (code_verifier, code_challenge S256).
    Obligatoire pour les External Client Apps (Salesforce Spring '26)."""
    verifier = secrets.token_urlsafe(64)  # 86 caractères ∈ [43, 128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def authorize_url(state: str, code_challenge: str) -> str:
    """URL de consentement Salesforce (le navigateur y est redirigé)."""
    params = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": settings.SF_CLIENT_ID,
            "redirect_uri": settings.SF_REDIRECT_URI,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{settings.SF_LOGIN_URL}/services/oauth2/authorize?{params}"


async def _token_request(data: dict[str, str]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
        response = await http.post(f"{settings.SF_LOGIN_URL}/services/oauth2/token", data=data)
    if response.status_code != 200:
        # Le corps d'erreur OAuth ne contient pas de jeton : loggable.
        logger.warning(
            "sf_token_request_failed",
            grant_type=data.get("grant_type"),
            status=response.status_code,
        )
        raise CRMAuthError(f"Échange de jeton Salesforce refusé ({response.status_code})")
    result: dict[str, Any] = response.json()
    return result


async def exchange_code(code: str, code_verifier: str) -> dict[str, Any]:
    """Échange le code d'autorisation contre access/refresh token + instance_url."""
    return await _token_request(
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": settings.SF_CLIENT_ID,
            "client_secret": settings.SF_CLIENT_SECRET,
            "redirect_uri": settings.SF_REDIRECT_URI,
            "code_verifier": code_verifier,
        }
    )


async def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    """Nouveau access token à partir du refresh token (qui reste valable)."""
    return await _token_request(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.SF_CLIENT_ID,
            "client_secret": settings.SF_CLIENT_SECRET,
        }
    )


async def revoke_token(token: str) -> None:
    """Révocation best-effort à la déconnexion (l'échec n'est pas bloquant)."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            await http.post(
                f"{settings.SF_LOGIN_URL}/services/oauth2/revoke", data={"token": token}
            )
    except httpx.HTTPError:
        logger.warning("sf_revoke_failed")


# --- Client REST (CRMPort) ------------------------------------------------

# Persistance du jeton rafraîchi (la fabrique re-chiffre en base).
OnRefresh = Callable[[dict[str, Any]], Awaitable[None]]


class SalesforceClient:
    """Un client = une organisation (jamais partagé entre orgs — la fabrique
    en construit un par appel). Utilisable en `async with` pour fermer la
    connexion HTTP proprement."""

    def __init__(
        self,
        instance_url: str,
        access_token: str,
        refresh_token: str,
        *,
        on_refresh: OnRefresh | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._instance_url = instance_url.rstrip("/")
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._on_refresh = on_refresh
        self._http = httpx.AsyncClient(timeout=_TIMEOUT, transport=transport)
        # Un seul échange de jeton à la fois par client (voir _refresh_once).
        self._refresh_lock = asyncio.Lock()

    async def __aenter__(self) -> "SalesforceClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(
        self, method: str, path: str, *, params: dict[str, str] | None = None, json: Any = None
    ) -> httpx.Response:
        """Requête authentifiée ; sur 401 : refresh puis rejeu UNE seule fois."""
        url = f"{self._instance_url}{path}"
        for attempt in (1, 2):
            used_token = self._access_token
            response = await self._http.request(
                method,
                url,
                params=params,
                json=json,
                headers={"Authorization": f"Bearer {used_token}"},
            )
            if response.status_code != 401:
                return self._raise_for_status(response)
            if attempt == 2:
                break
            await self._refresh_once(used_token)
        raise CRMAuthError("Jeton Salesforce invalide même après refresh — reconnexion requise")

    async def _refresh_once(self, used_token: str) -> None:
        """Renouvelle le jeton, UNE fois pour tous les appels concurrents.

        L'outil composite lance plusieurs requêtes en parallèle : à
        l'expiration, elles prennent toutes un 401 en même temps. Sans ce
        verrou, chacune échangerait le même refresh token — or Salesforce le
        fait tourner (rotation), si bien que tous les jetons obtenus sauf un
        sont aussitôt invalidés et que celui persisté en base peut être un
        jeton mort : la connexion de l'organisation est perdue à la prochaine
        expiration. Celui qui obtient le verrou rafraîchit ; les autres
        constatent que le jeton a changé et rejouent simplement leur requête.
        """
        async with self._refresh_lock:
            if self._access_token != used_token:
                return  # déjà rafraîchi par un appel concurrent
            logger.info("sf_token_expired_refreshing", instance=self._instance_url)
            tokens = await refresh_access_token(self._refresh_token)
            self._access_token = str(tokens["access_token"])
            # Rotation : le nouveau refresh token remplace l'ancien, y compris
            # pour les rafraîchissements suivants de CE client.
            if tokens.get("refresh_token"):
                self._refresh_token = str(tokens["refresh_token"])
            if self._on_refresh is not None:
                await self._on_refresh(tokens)

    def _raise_for_status(self, response: httpx.Response) -> httpx.Response:
        if response.status_code < 400:
            return response
        body = response.text[:300]  # messages d'erreur SF, jamais de jeton
        if response.status_code == 429 or "REQUEST_LIMIT_EXCEEDED" in body:
            raise CRMRateLimited(f"Quota API Salesforce atteint ({response.status_code})")
        if response.status_code == 403:
            raise CRMError(f"Accès refusé par Salesforce : {body}")
        raise CRMError(f"Erreur Salesforce {response.status_code} : {body}")

    # --- CRMPort ----------------------------------------------------------

    async def query(self, soql: str) -> list[dict[str, Any]]:
        response = await self._request(
            "GET", f"/services/data/{API_VERSION}/query", params={"q": soql}
        )
        payload = response.json()
        records = [self._clean(r) for r in payload.get("records", [])]
        while not payload.get("done", True) and payload.get("nextRecordsUrl"):
            response = await self._request("GET", str(payload["nextRecordsUrl"]))
            payload = response.json()
            records += [self._clean(r) for r in payload.get("records", [])]
        return records

    async def get(self, object: str, id: str) -> dict[str, Any]:
        response = await self._request(
            "GET", f"/services/data/{API_VERSION}/sobjects/{object}/{id}"
        )
        return self._clean(response.json())

    async def create(self, object: str, data: dict[str, Any]) -> str:
        response = await self._request(
            "POST", f"/services/data/{API_VERSION}/sobjects/{object}", json=data
        )
        return str(response.json()["id"])

    async def update(self, object: str, id: str, data: dict[str, Any]) -> None:
        await self._request(
            "PATCH", f"/services/data/{API_VERSION}/sobjects/{object}/{id}", json=data
        )

    @staticmethod
    def _clean(record: dict[str, Any]) -> dict[str, Any]:
        """Retire les métadonnées `attributes` pour matcher le contrat du port."""
        return {k: v for k, v in record.items() if k != "attributes"}
