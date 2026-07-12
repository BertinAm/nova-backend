"""Opt-in training-data sample: an image the on-device model handled
poorly (low confidence, error, or explicit negative feedback), uploaded
by a consenting user for future retraining. Stored on Hugging Face
Hub — this row is only local provenance/audit metadata, never the image
itself (Render's disk is ephemeral and not meant for a growing dataset).
"""
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TrainingSample(Base):
    __tablename__ = "training_samples"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    module_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hf_dataset_path: Mapped[str] = mapped_column(String(300), nullable=False)
    uploaded_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped["User | None"] = relationship()  # noqa: F821
