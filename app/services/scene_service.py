"""Business logic for scene description (MOD-03).

Images are processed entirely in memory and never written to disk or
the database, per FR-03-08 / NFR-28.
"""
from app.logging_config import audit_log, get_logger
from app.ml.scene_describer import SceneDescriber

logger = get_logger(__name__)

MAX_DESCRIPTION_WORDS = 80


class SceneService:
    async def describe(self, image_bytes: bytes, user_id: str | None) -> str:
        description = await SceneDescriber.describe(image_bytes)
        words = description.split()
        if len(words) > MAX_DESCRIPTION_WORDS:
            description = " ".join(words[:MAX_DESCRIPTION_WORDS])

        audit_log("scene.described", user_id=user_id, description_length=len(description))
        return description
