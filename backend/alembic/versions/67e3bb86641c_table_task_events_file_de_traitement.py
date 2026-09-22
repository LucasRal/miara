"""Journal des exécutions Celery (file de traitement)

Une tâche Celery ne laissait jusqu'ici qu'une ligne de log : impossible de
montrer dans l'application ce qui tourne, ce qui a échoué et pourquoi. Cette
table reçoit une ligne par EXÉCUTION, écrite par les signaux du worker
(`app/core/task_events.py`) : ouverte au démarrage, complétée à la fin avec la
durée et, en cas d'échec, le type et le message de l'erreur.

Une relance ne réécrit pas la ligne d'origine : elle publie une nouvelle
exécution, donc une nouvelle ligne, et incrémente `retried` sur l'ancienne.
C'est pourquoi rien n'a le droit de supprimer une ligne.

`args_json` ne contient que les arguments positionnels de la tâche (des
identifiants), jamais un contenu de CV ni un token.

Revision ID: 67e3bb86641c
Revises: 3cd1f0a7b2e4
Create Date: 2026-09-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "67e3bb86641c"
down_revision: str | Sequence[str] | None = "3cd1f0a7b2e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_events",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("queue", sa.String(length=30), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("args_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("trace_id", sa.Uuid(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("retried", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_task_events_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_events")),
    )
    op.create_index(op.f("ix_task_events_name"), "task_events", ["name"], unique=False)
    op.create_index(
        op.f("ix_task_events_organization_id"), "task_events", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_task_events_status"), "task_events", ["status"], unique=False)
    op.create_index(op.f("ix_task_events_task_id"), "task_events", ["task_id"], unique=False)
    op.create_index(op.f("ix_task_events_trace_id"), "task_events", ["trace_id"], unique=False)

    # --- Row-Level Security (ADR-002) : même politique que le socle ---------
    # Une organisation ne voit que SES tâches, y compris dans la file de
    # traitement : le worker écrit avec l'org portée par la tâche.
    op.execute("ALTER TABLE task_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE task_events FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_task_events ON task_events "
        "USING (organization_id = NULLIF(current_setting('app.current_org', true), '')::uuid)"
    )
    # Le worker insère puis complète la ligne ; l'écran incrémente le compteur
    # de relances. Rien ne supprime une trace d'exécution.
    op.execute("GRANT SELECT, INSERT, UPDATE ON task_events TO miara_app")


def downgrade() -> None:
    op.drop_index(op.f("ix_task_events_trace_id"), table_name="task_events")
    op.drop_index(op.f("ix_task_events_task_id"), table_name="task_events")
    op.drop_index(op.f("ix_task_events_status"), table_name="task_events")
    op.drop_index(op.f("ix_task_events_organization_id"), table_name="task_events")
    op.drop_index(op.f("ix_task_events_name"), table_name="task_events")
    op.drop_table("task_events")
