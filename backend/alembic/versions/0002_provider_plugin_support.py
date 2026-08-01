"""provider plugin support: CUSTOM enum value + Provider.plugin_id

Revision ID: 0002_provider_plugin_support
Revises: 0001_initial_schema
Create Date: 2026-08-01
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_provider_plugin_support"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres requires ADD VALUE to run outside an explicit multi-statement
    # transaction block in older server versions; Alembic's autocommit block
    # handles this safely on the versions targeted by this project.
    op.execute("ALTER TYPE provider_type ADD VALUE IF NOT EXISTS 'custom'")
    op.add_column(
        "provider",
        sa.Column("plugin_id", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    # Postgres cannot drop a single enum value; downgrading the enum requires
    # rebuilding the type, which is out of scope for this additive slice —
    # documented rather than silently omitted (Article V).
    op.drop_column("provider", "plugin_id")
