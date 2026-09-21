"""Récupération contextuelle structurée : mise en forme DÉTERMINISTE sous budget.

Cœur de l'hypothèse H3 du mémoire (chap. 5 et 8) : ce n'est pas le modèle qui
décide ce qui entre dans sa fenêtre de contexte, c'est ce module. Aucune part
d'aléatoire, aucun appel LLM ici — mêmes données en entrée, même texte en
sortie, mêmes compteurs.

Règles (ADR-008) :
- ordre de priorité fixe : en-tête du compte > opportunités ouvertes >
  activités de moins de 30 jours > contacts > cas ouverts > activités plus
  anciennes ;
- troncature PAR SECTION : on remplit section par section tant que le budget
  tient, et chaque élément écarté est compté ;
- texte compact plutôt que JSON (moins de jetons pour la même information),
  avec les ids d'enregistrements conservés pour que l'agent cite ses sources ;
- `tokens_used` et `items_dropped` sont retournés pour être journalisés.

Le budget est fixé par la configuration (`SALES_CONTEXT_BUDGET_TOKENS`), jamais
par le modèle (section NE PAS de la carte).
"""

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Fenêtre « activités chaudes » : au-delà, une activité passe en fin de priorité.
RECENT_DAYS = 30

# Mesure des jetons : l'encodage cl100k_base sert d'ÉTALON de mesure commun,
# pas de choix de modèle (ADR-011 vise les modèles, pas les tokenizers). Si
# tiktoken est indisponible, repli sur une estimation par caractères.
_CHARS_PER_TOKEN = 4


def _encoder() -> Any | None:
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception:  # pragma: no cover - dépend de l'environnement
        logger.warning("tiktoken_indisponible_estimation_par_caracteres")
        return None


_ENCODER = _encoder()


def count_tokens(text: str) -> int:
    if _ENCODER is not None:
        return len(_ENCODER.encode(text))
    return math.ceil(len(text) / _CHARS_PER_TOKEN)


# Place gardée pour la mention d'omission, toujours écrite en dernier.
_NOTE_RESERVE = count_tokens("[9999 élément(s) omis : budget de contexte atteint]")


@dataclass(frozen=True)
class BuiltContext:
    """Texte prêt pour le modèle + compteurs journalisés (chap. 8)."""

    text: str
    tokens_used: int
    items_dropped: int
    # Éléments retenus / disponibles par section, pour la courbe budget/qualité.
    sections: dict[str, tuple[int, int]]


def _euros(amount: float | None) -> str:
    if amount is None:
        return "montant inconnu"
    return f"{amount:,.0f} €".replace(",", " ")


def _account_header(account: dict[str, Any]) -> str:
    bits = [f"COMPTE {account.get('name') or '?'} ({account['id']})"]
    if account.get("industry"):
        bits.append(f"secteur {account['industry']}")
    if account.get("phone"):
        bits.append(f"tél {account['phone']}")
    if account.get("website"):
        bits.append(str(account["website"]))
    return " — ".join(bits)


def _opportunity_line(opp: dict[str, Any]) -> str:
    return (
        f"- {opp.get('name') or '?'} ({opp['id']}) | étape {opp.get('stage') or '?'} "
        f"| {_euros(opp.get('amount'))} | clôture prévue {opp.get('close_date') or '?'}"
    )


def _activity_line(act: dict[str, Any]) -> str:
    kind = "tâche" if act.get("type") == "Task" else "événement"
    status = f" [{act['status']}]" if act.get("status") else ""
    return f"- {act.get('date') or '?'} {kind} : {act.get('subject') or '?'} ({act['id']}){status}"


def _contact_line(contact: dict[str, Any]) -> str:
    bits = [f"- {contact.get('name') or '?'} ({contact['id']})"]
    for key in ("title", "email", "phone"):
        if contact.get(key):
            bits.append(str(contact[key]))
    return " — ".join(bits)


def _case_line(case: dict[str, Any]) -> str:
    return (
        f"- #{case.get('case_number') or '?'} ({case['id']}) {case.get('subject') or '?'} "
        f"| {case.get('status') or '?'} | priorité {case.get('priority') or '?'}"
    )


def _split_activities(
    activities: list[dict[str, Any]], today: date
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(chaudes, anciennes) selon RECENT_DAYS ; une date absente = ancienne."""
    cutoff = (today - timedelta(days=RECENT_DAYS)).isoformat()
    recent = [a for a in activities if (a.get("date") or "") >= cutoff]
    older = [a for a in activities if (a.get("date") or "") < cutoff]
    return recent, older


def build(
    account_context: dict[str, Any],
    budget_tokens: int = 3000,
    today: date | None = None,
) -> BuiltContext:
    """Rend le contexte d'un compte en texte compact sous `budget_tokens`.

    `account_context` est la sortie de l'outil composite `get_account_context`
    (modèles `app.sales.tools.schemas`, déjà sérialisés en dict).
    """
    today = today or date.today()
    recent, older = _split_activities(list(account_context.get("recent_activities") or []), today)

    # L'ordre de cette liste EST la priorité. Ne pas la réordonner ailleurs
    # (surtout pas dans le prompt : section NE PAS de la carte).
    plan: list[tuple[str, str, list[str]]] = [
        (
            "opportunites_ouvertes",
            "OPPORTUNITÉS OUVERTES",
            [_opportunity_line(o) for o in account_context.get("open_opportunities") or []],
        ),
        (
            "activites_recentes",
            f"ACTIVITÉS DES {RECENT_DAYS} DERNIERS JOURS",
            [_activity_line(a) for a in recent],
        ),
        (
            "contacts",
            "CONTACTS",
            [_contact_line(c) for c in account_context.get("contacts") or []],
        ),
        (
            "cas_ouverts",
            "CAS OUVERTS",
            [_case_line(c) for c in account_context.get("open_cases") or []],
        ),
        (
            "activites_anciennes",
            "ACTIVITÉS PLUS ANCIENNES",
            [_activity_line(a) for a in older],
        ),
    ]

    # L'en-tête du compte est l'ancre du briefing : jamais tronquée.
    lines = [_account_header(account_context["account"])]
    dropped = 0
    sections: dict[str, tuple[int, int]] = {}
    # Le budget porte sur le TEXTE FINAL : on mesure le texte assemblé à chaque
    # ajout (pas une somme de coûts par ligne, qui dérive) et on réserve de
    # quoi écrire la mention d'omission.
    ceiling = budget_tokens - _NOTE_RESERVE

    for key, title, items in plan:
        if not items:
            sections[key] = (0, 0)
            continue
        kept = 0
        title_written = False
        for item in items:
            candidate = [*lines, *([] if title_written else [title]), item]
            if count_tokens("\n".join(candidate)) > ceiling:
                dropped += len(items) - kept
                break
            lines = candidate
            title_written = True
            kept += 1
        sections[key] = (kept, len(items))

    if dropped:
        lines.append(f"[{dropped} élément(s) omis : budget de contexte atteint]")

    text = "\n".join(lines)
    used = count_tokens(text)  # mesure du texte réellement produit
    logger.info(
        "sales_context_built",
        account_id=account_context["account"]["id"],
        budget_tokens=budget_tokens,
        tokens_used=used,
        items_dropped=dropped,
    )
    return BuiltContext(text=text, tokens_used=used, items_dropped=dropped, sections=sections)
