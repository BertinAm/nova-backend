"""Business logic for syncing offline usage events and feedback."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models.usage_event import UsageEvent
from app.models.user_feedback import UserFeedback
from app.schemas.logs import FeedbackBatch, UsageEventBatch

logger = get_logger(__name__)


class LogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def batch_sync_events(self, batch: UsageEventBatch, user_id: str | None) -> tuple[int, int]:
        """Idempotently insert usage events. Duplicate IDs are skipped."""
        inserted = 0
        for event_data in batch.events:
            existing = await self.db.get(UsageEvent, event_data.id)
            if existing is not None:
                continue
            event = UsageEvent(
                id=event_data.id,
                user_id=user_id,
                module_id=event_data.module_id,
                event_timestamp=event_data.timestamp,
                outcome=event_data.outcome,
                confidence_score=event_data.confidence_score,
            )
            self.db.add(event)
            inserted += 1
        await self.db.flush()
        return inserted, len(batch.events)

    async def batch_sync_feedback(self, batch: FeedbackBatch) -> tuple[int, int]:
        inserted = 0
        for item in batch.feedback:
            existing = await self.db.get(UserFeedback, item.id)
            if existing is not None:
                continue
            feedback = UserFeedback(
                id=item.id,
                event_id=item.event_id,
                is_positive=item.is_positive,
                feedback_timestamp=item.timestamp,
            )
            self.db.add(feedback)
            inserted += 1
        await self.db.flush()
        return inserted, len(batch.feedback)
