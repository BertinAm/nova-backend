"""Usage telemetry ORM model. Contains no PII or raw sensor data."""
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    module_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    event_timestamp: Mapped[DateTime] = mapped_column(DateTime, nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    received_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped["User | None"] = relationship(back_populates="usage_events")  # noqa: F821
    feedback: Mapped["UserFeedback | None"] = relationship(  # noqa: F821
        back_populates="event", uselist=False, cascade="all, delete-orphan"
    )
