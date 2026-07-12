"""model_file_data

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "model_registry",
        sa.Column("file_data", sa.LargeBinary, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("model_registry", "file_data")
