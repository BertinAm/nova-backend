"""User account ORM model."""
import uuid

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(10), default="en-CM", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Operator/admin accounts can manage the model registry (upload new
    # TFLite versions). Regular BVI users are never operators.
    is_operator: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Opt-in only: whether this user allows low-confidence/error/negative-
    # feedback frames to be uploaded (to Hugging Face) for future model
    # retraining. Off by default — the app must never capture or send
    # images without this being explicitly set true by the user.
    data_collection_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    enrolled_faces: Mapped[list["EnrolledFace"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    usage_events: Mapped[list["UsageEvent"]] = relationship(back_populates="user")  # noqa: F821
    emergency_contact: Mapped["EmergencyContact | None"] = relationship(  # noqa: F821
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email}>"
