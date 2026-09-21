"""Point d'injection FastAPI de la passerelle LLM.

Un SEUL objet de dépendance pour tout le monolithe : les tests surchargent
`gateway_dependency` une fois et scriptent aussi bien les agents commerciaux
que l'extraction RH. Un module métier n'a ainsi pas à importer un autre module
métier pour obtenir sa passerelle.
"""

from app.core.llm.gateway import LLMGateway, get_gateway


def gateway_dependency() -> LLMGateway:
    """Passerelle LLM injectée (surchargeable dans les tests)."""
    return get_gateway()
