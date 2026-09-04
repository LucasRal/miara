"""politique member_self_access sur memberships

Un utilisateur voit ses PROPRES memberships via `app.current_user`, sans
`app.current_org` posé : indispensable au login (« lister mes organisations »
avant d'avoir choisi une organisation). Les politiques permissives se
combinent en OR avec `tenant_isolation_memberships` ; le WITH CHECK implicite
autorise aussi l'insertion de sa propre membership (création d'organisation).

Revision ID: f5f62cf40791
Revises: 404c0385dd08
Create Date: 2026-09-04 04:20:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5f62cf40791"
down_revision: str | Sequence[str] | None = "404c0385dd08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "CREATE POLICY member_self_access ON memberships "
        "USING (user_id = "
        "NULLIF(current_setting('app.current_user', true), '')::uuid)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP POLICY member_self_access ON memberships")
