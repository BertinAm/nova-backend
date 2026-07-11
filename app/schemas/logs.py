"""Request/response schemas for usage log and feedback sync."""
from datetime import datetime

from pydantic import BaseModel, Field


class UsageEventIn(BaseModel):
    id: str = Field(description="Client-generated UUID, used for idempotent sync")
    module_id: str = Field(pattern=r"^MOD-0[1-5]$")
    timestamp: datetime
    outcome: str
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)


class UsageEventBatch(BaseModel):
    events: list[UsageEventIn]


class SyncResponse(BaseModel):
    inserted: int
    total: int


class FeedbackIn(BaseModel):
    id: str
    event_id: str
    is_positive: bool
    timestamp: datetime


class FeedbackBatch(BaseModel):
    feedback: list[FeedbackIn]
