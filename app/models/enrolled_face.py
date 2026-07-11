"""Enrolled face embedding ORM model.

Only the AES-256 (Fernet) encrypted 512-d embedding vector is stored. Raw
face images are never persisted (see FR-05-08 / NFR-27 in the SRS).
"""
import uuid

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EnrolledFace(Base):
    __tablename__ = "enrolled_faces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_name: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="enrolled_faces")  # noqa: F821
