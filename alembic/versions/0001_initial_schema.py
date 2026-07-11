"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-06-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("preferred_language", sa.String(10), nullable=False, server_default="en-CM"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_index("idx_users_email", "users", ["email"])

    op.create_table(
        "enrolled_faces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_name", sa.String(100), nullable=False),
        sa.Column("embedding_encrypted", sa.LargeBinary, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_enrolled_faces_user_id", "enrolled_faces", ["user_id"])

    op.create_table(
        "usage_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("module_id", sa.String(20), nullable=False),
        sa.Column("event_timestamp", sa.DateTime, nullable=False),
        sa.Column("outcome", sa.String(50), nullable=False),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("device_id", sa.String(64), nullable=True),
        sa.Column("received_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_usage_events_user_id", "usage_events", ["user_id"])
    op.create_index("idx_usage_events_module_id", "usage_events", ["module_id"])
    op.create_index("idx_usage_events_timestamp", "usage_events", ["event_timestamp"])

    op.create_table(
        "user_feedbacks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("usage_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_positive", sa.Boolean, nullable=False),
        sa.Column("feedback_timestamp", sa.DateTime, nullable=False),
        sa.Column("synced_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_user_feedbacks_event_id", "user_feedbacks", ["event_id"])

    op.create_table(
        "model_registry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("module_id", sa.String(20), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("hf_repo_url", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("uploaded_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
    )
    op.create_unique_constraint(
        "uq_model_registry_module_version", "model_registry", ["module_id", "version"]
    )
    op.create_index("idx_model_registry_module_id", "model_registry", ["module_id"])

    op.create_table(
        "emergency_contacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_name", sa.String(100), nullable=False),
        sa.Column("phone_encrypted", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_emergency_contacts_user_id", "emergency_contacts", ["user_id"])


def downgrade() -> None:
    op.drop_table("emergency_contacts")
    op.drop_table("model_registry")
    op.drop_table("user_feedbacks")
    op.drop_table("usage_events")
    op.drop_table("enrolled_faces")
    op.drop_table("users")
