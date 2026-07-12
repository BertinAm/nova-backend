"""SQLAlchemy ORM models.

Imported together so that Alembic's autogenerate can discover all tables via
``Base.metadata``.
"""
from app.models.emergency_contact import EmergencyContact
from app.models.enrolled_face import EnrolledFace
from app.models.model_registry import ModelRegistry
from app.models.training_sample import TrainingSample
from app.models.usage_event import UsageEvent
from app.models.user import User
from app.models.user_feedback import UserFeedback

__all__ = [
    "User",
    "EnrolledFace",
    "UsageEvent",
    "UserFeedback",
    "ModelRegistry",
    "EmergencyContact",
    "TrainingSample",
]
