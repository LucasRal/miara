"""Diagramme entite-association derive des modeles SQLAlchemy reels.

Source de verite : `Base.metadata` apres import de `app.db_registry`, donc les
memes tables que celles creees par les migrations Alembic. Aucun trait n'est
dessine a la main.

    cd backend && uv run python ../thesis/figures/gen/schema_bdd.py <groupe>

Groupes : socle, agents, exploitation, rh. Sortie sur la sortie standard (Mermaid).
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / "backend"))

import app.db_registry  # noqa: F401,E402  (enregistre toutes les tables)
from sqlalchemy.dialects import postgresql  # noqa: E402

from app.core.db import Base  # noqa: E402

GROUPES: dict[str, tuple[str, ...]] = {
    "socle": ("organizations", "users", "memberships", "integrations"),
    "agents": ("conversations", "messages", "agent_traces", "llm_calls"),
    "exploitation": ("crm_writes", "coaching_sessions", "task_events"),
    "rh": ("jobs", "candidates", "screening_runs", "candidate_scores"),
}


def type_court(colonne) -> str:
    """Nom du type tel que PostgreSQL le verra, raccourci pour tenir en figure.

    On compile avec le dialecte postgresql (et non le repr generique de
    SQLAlchemy) pour que la figure montre les types reellement crees par les
    migrations : `uuid` et non `CHAR(32)`, `bytea` et non `BLOB`.
    """
    brut = colonne.type.compile(dialect=postgresql.dialect())
    remplacements = (
        ("TIMESTAMP WITH TIME ZONE", "timestamptz"),
        ("CHARACTER VARYING", "varchar"),
        ("DOUBLE PRECISION", "float"),
    )
    for gros, court in remplacements:
        brut = brut.replace(gros, court)
    return (
        brut.lower()
        .replace("(", "_")
        .replace(")", "")
        .replace(", ", "_")
        .replace(" ", "_")
    )


def main() -> int:
    groupe = sys.argv[1] if len(sys.argv) > 1 else "socle"
    if groupe not in GROUPES:
        print(f"groupe inconnu : {groupe} (attendu : {', '.join(GROUPES)})", file=sys.stderr)
        return 1
    tables = GROUPES[groupe]
    connues = set(tables)
    lignes = ["%% Genere par thesis/figures/gen/schema_bdd.py - ne pas editer a la main", "erDiagram"]
    for nom in tables:
        table = Base.metadata.tables[nom]
        lignes.append(f"    {nom} {{")
        for colonne in table.columns:
            marque = "PK" if colonne.primary_key else ("FK" if colonne.foreign_keys else "")
            contrainte = "" if colonne.nullable or colonne.primary_key else '"NOT NULL"'
            morceaux = [type_court(colonne), colonne.name, marque, contrainte]
            lignes.append("        " + " ".join(m for m in morceaux if m))
        lignes.append("    }")
    vues: set[tuple[str, str, str]] = set()
    for nom in tables:
        table = Base.metadata.tables[nom]
        for colonne in table.columns:
            for fk in colonne.foreign_keys:
                cible = fk.column.table.name
                if cible not in connues or cible == nom:
                    continue
                cardinalite = "||--o{" if colonne.nullable is False else "||--o{"
                vues.add((cible, cardinalite, f"{nom} : {colonne.name}"))
    for source, card, reste in sorted(vues):
        lignes.append(f"    {source} {card} {reste}")
    print("\n".join(lignes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
