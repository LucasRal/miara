"""Évaluation du coach commercial contre l'annotation humaine (chap. 8).

Trois mesures, avec le VRAI modèle :
- accord de rang (Spearman) entre `overall_0_100` et l'annotation manuelle du
  jeu doré — critère de la carte : rho >= 0,7 ;
- preuve citée : part des critères dont l'`evidence` est un extrait littéral
  du texte évalué (le reste devant être un constat d'absence explicite) ;
- résistance à l'injection : le même texte, avec une consigne « donne 100/100 »
  ajoutée dedans, doit garder sa note.

    uv run python -m scripts.eval_coach --org <uuid> [--limit N]
"""

import argparse
import asyncio
import json
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Any

import app.db_registry  # noqa: F401  (enregistre tous les modèles : FK résolues)
from app.core.agents import Final, RequestContext, run
from app.sales.agents.coach import CoachingFeedback, sales_coach, wrap_user_text
from scripts.bench_sales_assistant import first_member

GOLDEN_PATH = Path(__file__).resolve().parent / "data" / "golden_coach_v1.json"


def _normalize(text: str) -> str:
    """Comparaison tolérante : sans accents, sans ponctuation, en minuscules."""
    stripped = "".join(
        c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", stripped).strip()


# Marqueurs d'un constat d'absence : une preuve valable quand le texte ne
# contient rien à citer pour ce critère.
_ABSENCE = re.compile(
    r"aucun|aucune|pas de |pas d'|n'est|ne mentionne|ne contient|sans |absence|non trait",
    re.IGNORECASE,
)
# Jugement sur la forme du texte (critère « ton et concision » surtout).
_APPRECIATION = re.compile(
    r"\bton\b|concis|clair|structur|professionnel|familier|verbeu|lisib|longueur",
    re.IGNORECASE,
)


def classify_evidence(evidence: str, source: str) -> str:
    """citation | constat | appreciation | autre.

    « citation » couvre aussi les citations élidées (« début… fin ») : chaque
    fragment doit se retrouver dans le texte. « autre » est le seul cas
    problématique — une preuve qui ne renvoie à rien de vérifiable.
    """
    fragments = [f for f in re.split(r"\.{3}|…", evidence) if len(f.strip()) >= 12]
    if fragments and all(_is_literal_quote(f, source) for f in fragments):
        return "citation"
    if _ABSENCE.search(evidence):
        return "constat"
    # Jugement global (ton, longueur) : légitime, mais non vérifiable mot à mot.
    return "appreciation" if _APPRECIATION.search(evidence) else "autre"


def _is_literal_quote(evidence: str, source: str) -> bool:
    """`evidence` reprend-elle un extrait du texte (hors guillemets) ?"""
    inner = evidence.strip().strip("«»\"'").strip()
    if len(inner) < 12:
        return False
    return _normalize(inner) in _normalize(source)


def _ranks(values: list[float]) -> list[float]:
    """Rangs moyens (ex aequo partagés) — base du rho de Spearman."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float:
    rx, ry = _ranks(xs), _ranks(ys)
    n = len(xs)
    mean_x, mean_y = sum(rx) / n, sum(ry) / n
    cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry, strict=True))
    var_x = sum((a - mean_x) ** 2 for a in rx)
    var_y = sum((b - mean_y) ** 2 for b in ry)
    return cov / (var_x * var_y) ** 0.5 if var_x and var_y else 0.0


async def _evaluate(
    org_id: uuid.UUID, user_id: uuid.UUID, text: str, kind: str
) -> CoachingFeedback:
    ctx = RequestContext(org_id=org_id, user_id=user_id, role="sales")
    result = await run(sales_coach, wrap_user_text(text, kind), ctx)
    if not isinstance(result, Final) or not isinstance(result.structured, CoachingFeedback):
        raise RuntimeError(f"Sortie inexploitable : {type(result).__name__}")
    return result.structured


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", required=True, help="UUID de l'organisation")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--json", type=Path, help="écrit les mesures détaillées")
    args = parser.parse_args()

    org_id = uuid.UUID(args.org)
    user_id = await first_member(org_id)
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    notes = golden["notes"][: args.limit] if args.limit else golden["notes"]

    rows: list[dict[str, Any]] = []
    kinds_of_evidence: dict[str, int] = {
        "citation": 0,
        "constat": 0,
        "appreciation": 0,
        "autre": 0,
    }
    criteria_total = 0
    for note in notes:
        feedback = await _evaluate(org_id, user_id, note["text"], note["kind"])
        classes = [classify_evidence(c.evidence, note["text"]) for c in feedback.criteria]
        for c in classes:
            kinds_of_evidence[c] += 1
        literal = [c == "citation" for c in classes]
        criteria_total += len(literal)
        rows.append(
            {
                "id": note["id"],
                "kind": note["kind"],
                "reference": note["reference_0_100"],
                "coach": feedback.overall_0_100,
                "scores": feedback.scores(),
                "literal_quotes": f"{sum(literal)}/{len(literal)}",
                "evidence_classes": classes,
                "feedback": feedback.model_dump(mode="json"),
            }
        )
        ecart = feedback.overall_0_100 - note["reference_0_100"]
        print(
            f"{note['id']} {note['kind']:<10} humain={note['reference_0_100']:>3} "
            f"coach={feedback.overall_0_100:>3}  écart={ecart:>+4}"
            f"  preuves littérales={sum(literal)}/{len(literal)}"
        )

    rho = spearman(
        [float(r["reference"]) for r in rows],
        [float(r["coach"]) for r in rows],
    )
    ecarts = [abs(r["coach"] - r["reference"]) for r in rows]

    # --- injection : même texte, consigne hostile ajoutée dedans -----------
    print("\n--- Résistance à l'injection ---")
    injections: list[dict[str, Any]] = []
    for note in (notes[0], notes[-1]):
        clean = next(r for r in rows if r["id"] == note["id"])["coach"]
        hostile = await _evaluate(
            org_id, user_id, note["text"] + golden["injection_suffix"], note["kind"]
        )
        injections.append(
            {"id": note["id"], "clean": clean, "injected": hostile.overall_0_100}
        )
        print(
            f"{note['id']} sans injection={clean:>3}  avec injection="
            f"{hostile.overall_0_100:>3}  écart={hostile.overall_0_100 - clean:>+4}"
        )

    print("\n--- Accord avec l'annotation humaine ---")
    print(f"textes            : {len(rows)}")
    print(f"Spearman rho      : {rho:.3f}  (critère : >= 0,700)")
    print(f"écart absolu moyen: {sum(ecarts) / len(ecarts):.1f} points")
    print(f"écart max         : {max(ecarts)} points")
    print(f"preuves           : {criteria_total} au total")
    for label, count in kinds_of_evidence.items():
        print(f"  {label:<16}: {count}")
    if args.json:
        detail = {"rows": rows, "rho": rho, "injections": injections}
        args.json.write_text(
            json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"détail écrit dans {args.json}")


if __name__ == "__main__":
    asyncio.run(main())
