"""User feedback (good/bad) linked one-to-one with a usage event."""
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserFeedback(Base):
    __tablename__ = "user_feedbacks"
    __table_args__ = (UniqueConstraint("event_id", name="uq_user_feedbacks_event_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(
        ForeignKey("usage_events.id", ondelete="CASCADE"), nullable=False
    )
    is_positive: Mapped[bool] = mapped_column(Boolean, nullable=False)
    feedback_timestamp: Mapped[DateTime] = mapped_column(DateTime, nullable=False)
    synced_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    event: Mapped["UsageEvent"] = relationship(back_populates="feedback")  # noqa: F821
