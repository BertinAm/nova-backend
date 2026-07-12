"""training_data_collection

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("data_collection_consent", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "training_samples",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("module_id", sa.String(20), nullable=False),
        sa.Column("outcome", sa.String(50), nullable=False),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("hf_dataset_path", sa.String(300), nullable=False),
        sa.Column("uploaded_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_training_samples_user_id", "training_samples", ["user_id"])
    op.create_index("ix_training_samples_module_id", "training_samples", ["module_id"])


def downgrade() -> None:
    op.drop_index("ix_training_samples_module_id", table_name="training_samples")
    op.drop_index("ix_training_samples_user_id", table_name="training_samples")
    op.drop_table("training_samples")
    op.drop_column("users", "data_collection_consent")
