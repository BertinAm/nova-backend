"""Request/response schemas for usage log and feedback sync."""
from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator


def _to_naive_utc(value: datetime) -> datetime:
    """Normalise an incoming timestamp to naive UTC.

    Mobile clients send standard ISO-8601 with a ``Z`` suffix (e.g. from
    JS/Dart ``.toISOString()``), which pydantic parses as timezone-aware.
    The ``event_timestamp``/``feedback_timestamp`` columns are naive
    ``DateTime`` (UTC implied) — asyncpg rejects binding a tz-aware
    datetime against them, so convert to UTC and strip tzinfo here, once,
    for every caller.
    """
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


class UsageEventIn(BaseModel):
    id: str = Field(description="Client-generated UUID, used for idempotent sync")
    module_id: str = Field(pattern=r"^MOD-0[1-5]$")
    timestamp: datetime
    outcome: str
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("timestamp")
    @classmethod
    def _normalize_timestamp(cls, v: datetime) -> datetime:
        return _to_naive_utc(v)


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

    @field_validator("timestamp")
    @classmethod
    def _normalize_timestamp(cls, v: datetime) -> datetime:
        return _to_naive_utc(v)


class FeedbackBatch(BaseModel):
    feedback: list[FeedbackIn]
