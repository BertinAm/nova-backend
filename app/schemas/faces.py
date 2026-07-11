"""Request/response schemas for the face recognition router."""
from pydantic import BaseModel, Field


class FaceEnrolResponse(BaseModel):
    face_id: str
    contact_name: str


class FaceMatchRequest(BaseModel):
    """Probe embedding sent by the mobile app, base64-encoded float32 bytes.

    The mobile app extracts the embedding on-device (or via the detect
    step) — raw face images are never required by this endpoint.
    """
    embedding_b64: str = Field(description="Base64-encoded 512-d float32 embedding")
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class FaceMatchResponse(BaseModel):
    match_found: bool
    contact_name: str | None = None
    similarity: float | None = None


class EnrolledFaceSummary(BaseModel):
    face_id: str
    contact_name: str
