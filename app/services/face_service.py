"""Business logic for face enrolment and matching (MOD-05).

Raw face images are never stored — only AES-256 encrypted ArcFace
embeddings (FR-05-08, NFR-27). Embedding comparison happens against the
calling user's own gallery only.
"""
import base64

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging_config import audit_log, get_logger
from app.ml.face_matcher import FaceMatcher
from app.models.enrolled_face import EnrolledFace
from app.security.crypto import decrypt_embedding, encrypt_embedding

settings = get_settings()
logger = get_logger(__name__)


class FaceNotDetectedError(ValueError):
    pass


class FaceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def enrol_face(self, user_id: str, contact_name: str, face_crop_bytes: bytes) -> EnrolledFace:
        embedding = await FaceMatcher.extract_embedding(face_crop_bytes)
        encrypted = encrypt_embedding(embedding)

        face = EnrolledFace(
            user_id=user_id,
            contact_name=contact_name,
            embedding_encrypted=encrypted,
        )
        self.db.add(face)
        await self.db.flush()

        audit_log("face.enrolled", user_id=user_id, face_id=face.id)
        return face

    async def match_face(
        self,
        user_id: str,
        probe_embedding_b64: str,
        threshold: float | None = None,
    ) -> tuple[bool, str | None, float]:
        threshold = threshold if threshold is not None else settings.FACE_MATCH_THRESHOLD
        probe = np.frombuffer(base64.b64decode(probe_embedding_b64), dtype=np.float32)

        result = await self.db.execute(select(EnrolledFace).where(EnrolledFace.user_id == user_id))
        enrolled = result.scalars().all()

        best_score = 0.0
        best_name: str | None = None
        for face in enrolled:
            gallery_embedding = decrypt_embedding(face.embedding_encrypted)
            score = FaceMatcher.cosine_similarity(probe, gallery_embedding)
            if score > best_score:
                best_score = score
                best_name = face.contact_name

        matched = best_score >= threshold
        audit_log(
            "face.match_attempted",
            user_id=user_id,
            matched=matched,
            similarity=round(best_score, 4),
        )
        return matched, (best_name if matched else None), best_score

    async def list_enrolled_faces(self, user_id: str) -> list[EnrolledFace]:
        result = await self.db.execute(select(EnrolledFace).where(EnrolledFace.user_id == user_id))
        return list(result.scalars().all())

    async def delete_enrolled_face(self, face_id: str, user_id: str) -> bool:
        face = await self.db.get(EnrolledFace, face_id)
        if not face or face.user_id != user_id:
            return False
        await self.db.delete(face)
        audit_log("face.deleted", user_id=user_id, face_id=face_id)
        return True
