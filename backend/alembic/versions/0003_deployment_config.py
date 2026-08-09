"""deployment config column

Revision ID: 0003_deployment_config
Revises: 0002_provider_plugin_support
Create Date: 2026-08-09
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_deployment_config"
down_revision: Union[str, None] = "0002_provider_plugin_support"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "deployment",
        sa.Column("config", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("deployment", "config")
