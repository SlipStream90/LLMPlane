"""Alembic migration: create user table for OAuth.

Revision ID: 0004_user_oauth
Revises: 0003_deployment_config
Create Date: 2026-08-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_user_oauth"
down_revision: Union[str, None] = "0003_deployment_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(1024), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_user_id", sa.String(255), nullable=False),
        sa.Column("last_login_at", sa.String(36), nullable=True),
        sa.Column("default_project_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_user_provider_id"),
    )
    op.create_index("ix_user_email", "user", ["email"])
    op.create_index("ix_user_provider", "user", ["provider"])


def downgrade() -> None:
    op.drop_index("ix_user_provider")
    op.drop_index("ix_user_email")
    op.drop_table("user")
