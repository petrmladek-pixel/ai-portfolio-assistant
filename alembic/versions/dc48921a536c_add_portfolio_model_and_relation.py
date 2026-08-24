"""Add portfolio model and relation

Revision ID: dc48921a536c
Revises: da98043cedc9
Create Date: 2026-08-21 15:36:05.382630

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "dc48921a536c"
down_revision: str | Sequence[str] | None = "da98043cedc9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Mark the duplicate historical revision as applied."""


def downgrade() -> None:
    """Leave the schema unchanged for the duplicate historical revision."""
