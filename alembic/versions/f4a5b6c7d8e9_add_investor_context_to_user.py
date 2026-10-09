"""Add the persisted investor context preference.

Revision ID: f4a5b6c7d8e9
Revises: f3a4b5c6d7e8
Create Date: 2026-10-08
"""

import sqlalchemy as sa

from alembic import op

revision = "f4a5b6c7d8e9"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the optional shared investor context to user preferences."""
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("users"):
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "investor_context" not in columns:
        op.add_column("users", sa.Column("investor_context", sa.String()))


def downgrade() -> None:
    """Remove the persisted investor context preference."""
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("users"):
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "investor_context" in columns:
        op.drop_column("users", "investor_context")
