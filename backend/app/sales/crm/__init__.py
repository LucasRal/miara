"""Accès CRM du module sales (ADR-005).

Tout accès CRM passe par `get_crm(ctx) -> CRMPort` ; l'API Salesforce n'est
appelée QUE dans `salesforce.py`.
"""

from app.sales.crm.factory import clear_fake, get_crm, register_fake
from app.sales.crm.fake import FakeCRM
from app.sales.crm.port import CRMAuthError, CRMError, CRMPort, CRMRateLimited
from app.sales.crm.salesforce import SalesforceClient

__all__ = [
    "CRMAuthError",
    "CRMError",
    "CRMPort",
    "CRMRateLimited",
    "FakeCRM",
    "SalesforceClient",
    "clear_fake",
    "get_crm",
    "register_fake",
]
