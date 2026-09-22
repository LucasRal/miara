"""Droit de suppression des candidatures et de leurs résultats

Le socle RH n'accordait que SELECT, INSERT, UPDATE sur les tables RH, avec la
note « la suppression d'un CV (droit à l'effacement) est ajoutée avec
l'endpoint correspondant ». Cet endpoint existe maintenant :

- `DELETE /hr/jobs/{job_id}/candidates/{id}` retire le CV et son fichier ;
- `POST /hr/runs/{id}/candidates/{id}/retry` efface la ligne de résultat en
  échec pour que la reprise ne se croie pas déjà faite.

Le privilège s'arrête là : ni `jobs`, ni `screening_runs` ne deviennent
supprimables. Effacer une campagne effacerait la trace d'une décision de
présélection, qui doit rester auditable.

Revision ID: 3cd1f0a7b2e4
Revises: 2ae74c5df3a8
Create Date: 2026-09-22

"""

from collections.abc import Sequence

from alembic import op

revision: str = "3cd1f0a7b2e4"
down_revision: str | Sequence[str] | None = "2ae74c5df3a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("candidates", "candidate_scores")


def upgrade() -> None:
    # La politique RLS de ces tables est déjà en USING sans restriction de
    # commande : elle couvre donc DELETE dès que le privilège est accordé.
    for table in TABLES:
        op.execute(f"GRANT DELETE ON {table} TO miara_app")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"REVOKE DELETE ON {table} FROM miara_app")
