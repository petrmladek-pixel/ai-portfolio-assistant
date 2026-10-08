"""Add the system demo-user marker.

Revision ID: f2a3b4c5d6e7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-07
"""

import sqlalchemy as sa

from alembic import op

revision = "f2a3b4c5d6e7"
down_revision = "c3d4e5f6a7b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Mark the dedicated system account used for public demo data."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        _create_users_table()
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "is_demo" not in columns:
        op.add_column(
            "users",
            sa.Column(
                "is_demo",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    indexes = {index["name"] for index in inspector.get_indexes("users")}
    index_name = op.f("ix_users_is_demo")
    if index_name not in indexes:
        op.create_index(index_name, "users", ["is_demo"], unique=False)


def downgrade() -> None:
    """Remove the system demo-user marker."""
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("users"):
        return
    indexes = {index["name"] for index in inspector.get_indexes("users")}
    index_name = op.f("ix_users_is_demo")
    if index_name in indexes:
        op.drop_index(index_name, table_name="users")
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "is_demo" in columns:
        op.drop_column("users", "is_demo")


def _create_users_table() -> None:
    """Create the user table required by the current portfolio schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "is_superuser",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("analysis_prompt", sa.String(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_is_demo"), "users", ["is_demo"], unique=False)
