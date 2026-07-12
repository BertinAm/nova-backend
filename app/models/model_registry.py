"""TFLite model version registry, used for OTA model updates.

Includes ``hf_repo_url`` per the database document's revision notes: the
mobile app needs a canonical source URL (HuggingFace repo) in addition to
the server-relative download path, so provenance of a deployed model is
always traceable.
"""
import uuid

from sqlalchemy import Boolean, DateTime, LargeBinary, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ModelRegistry(Base):
    __tablename__ = "model_registry"
    __table_args__ = (
        UniqueConstraint("module_id", "version", name="uq_model_registry_module_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    module_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    # The .tflite bytes themselves, stored in Postgres rather than on disk.
    # Render's free-tier filesystem is ephemeral and wiped on every
    # restart/redeploy — a model written to MODEL_STORAGE_PATH would
    # silently vanish (registry metadata survives in Postgres, but the
    # actual file doesn't), leaving /models/latest correct while
    # /models/download 404s. Postgres data survives redeploys; a few MB
    # per model version is negligible for the free-tier DB.
    file_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # Canonical origin of the model artifact (e.g. a HuggingFace repo URL),
    # kept separate from the server-relative download endpoint so the
    # registry retains provenance even if the file is re-hosted.
    hf_repo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    uploaded_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
