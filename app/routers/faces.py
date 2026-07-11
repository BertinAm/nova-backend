"""Face enrolment, matching, listing, and deletion (MOD-05)."""
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.ml.face_matcher import NoFaceDetectedError
from app.models.user import User
from app.rate_limit import limiter
from app.schemas.faces import (
    EnrolledFaceSummary,
    FaceEnrolResponse,
    FaceMatchRequest,
    FaceMatchResponse,
)
from app.services.face_service import FaceService

router = APIRouter(prefix="/faces", tags=["Face Recognition"])

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB cap for enrolment crops


@router.post("/enrol", response_model=FaceEnrolResponse, status_code=201)
@limiter.limit("20/minute")
async def enrol_face(
    request: Request,
    contact_name: str,
    face_crop: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Enrol a known contact from a face crop image. Only the encrypted
    embedding is persisted — the raw image is discarded after extraction
    (FR-05-01, FR-05-08).
    """
    image_bytes = await face_crop.read()
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(413, "Image too large")

    service = FaceService(db)
    try:
        face = await service.enrol_face(current_user.id, contact_name.strip(), image_bytes)
    except NoFaceDetectedError as exc:
        raise HTTPException(422, "No face detected in the provided image") from exc

    await db.commit()
    return FaceEnrolResponse(face_id=face.id, contact_name=face.contact_name)


@router.post("/match", response_model=FaceMatchResponse)
@limiter.limit("60/minute")
async def match_face(
    request: Request,
    body: FaceMatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Match a probe face embedding against the current user's enrolled
    gallery. Used for galleries exceeding the on-device limit (FR-05-04).
    """
    service = FaceService(db)
    matched, contact_name, similarity = await service.match_face(
        current_user.id, body.embedding_b64, body.threshold
    )
    return FaceMatchResponse(
        match_found=matched,
        contact_name=contact_name,
        similarity=round(similarity, 4),
    )


@router.get("/", response_model=list[EnrolledFaceSummary])
async def list_faces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List enrolled contacts (names only — no embeddings returned)."""
    service = FaceService(db)
    faces = await service.list_enrolled_faces(current_user.id)
    return [EnrolledFaceSummary(face_id=f.id, contact_name=f.contact_name) for f in faces]


@router.delete("/{face_id}", status_code=204)
async def delete_face(
    face_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an enrolled contact and its embedding (FR-05-09 — right to erasure)."""
    service = FaceService(db)
    deleted = await service.delete_enrolled_face(face_id, current_user.id)
    if not deleted:
        raise HTTPException(404, "Enrolled face not found")
    await db.commit()
