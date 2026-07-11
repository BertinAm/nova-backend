"""Response schemas for the operator admin dashboard."""
from datetime import datetime

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_users: int
    active_users: int
    operator_users: int
    total_enrolled_faces: int
    total_usage_events: int
    total_feedback: int
    positive_feedback_pct: float | None
    events_last_24h: int
    events_last_7d: int
    active_model_count: int
    module_ids_with_active_model: list[str]


class ModuleUsageStat(BaseModel):
    module_id: str
    total_events: int
    success_count: int
    error_count: int
    no_detection_count: int
    low_confidence_count: int
    offline_skip_count: int
    avg_confidence: float | None
    positive_feedback: int
    negative_feedback: int


class DailyEventCount(BaseModel):
    date: str
    count: int


class AdminUserSummary(BaseModel):
    id: str
    email: str
    preferred_language: str
    is_active: bool
    is_operator: bool
    created_at: datetime
    enrolled_face_count: int
    usage_event_count: int
    has_emergency_contact: bool


class AdminUserListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    users: list[AdminUserSummary]


class SetOperatorRequest(BaseModel):
    is_operator: bool


class SetActiveRequest(BaseModel):
    is_active: bool


class AdminModelSummary(BaseModel):
    id: str
    module_id: str
    version: str
    filename: str
    checksum: str
    hf_repo_url: str | None
    is_active: bool
    uploaded_at: datetime
    notes: str | None


class RecentEventSummary(BaseModel):
    id: str
    user_id: str | None
    user_email: str | None
    module_id: str
    event_timestamp: datetime
    outcome: str
    confidence_score: float | None
    feedback_positive: bool | None
