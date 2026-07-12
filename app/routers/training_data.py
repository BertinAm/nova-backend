"""Opt-in training-data collection: consent toggle + frame upload.

Only frames worth retraining on should ever reach here — low-confidence
detections, error/no_detection outcomes, or frames tied to explicit
negative feedback. That filtering decision is made on-device (mobile
app); this router just enforces consent and forwards to storage.
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.rate_limit import limiter
from app.schemas.training_data import (
    ConsentRequest,
    ConsentResponse,
    TrainingSampleUploadResponse,
)
from app.services.training_data_service import TrainingDataService

router = APIRouter(prefix="/training-data", tags=["Training Data Collection"])

VALID_MODULE_IDS = {"MOD-01", "MOD-02", "MOD-03", "MOD-04", "MOD-05"}
VALID_OUTCOMES = {"low_confidence", "error", "no_detection", "negative_feedback"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@router.get("/consent", response_model=ConsentResponse)
async def get_consent(current_user: User = Depends(get_current_user)):
    return ConsentResponse(data_collection_consent=current_user.data_collection_consent)


@router.put("/consent", response_model=ConsentResponse)
@limiter.limit("10/minute")
async def set_consent(
    request: Request,
    body: ConsentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Explicit opt-in/opt-out. Nothing is ever uploaded without this
    being set true first — see the consent check in /training-data/upload."""
    current_user.data_collection_consent = body.consent
    await db.commit()
    return ConsentResponse(data_collection_consent=current_user.data_collection_consent)


@router.post("/upload", response_model=TrainingSampleUploadResponse, status_code=201)
@limiter.limit("30/minute")
async def upload_sample(
    request: Request,
    module_id: str = Form(...),
    outcome: str = Form(...),
    confidence_score: float | None = Form(default=None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload one frame for future retraining. Requires the account to
    have opted in via PUT /training-data/consent — a 403 here, not a
    silent drop, so the mobile client can surface a clear "not opted in"
    state rather than retrying forever."""
    if not current_user.data_collection_consent:
        raise HTTPException(403, "Data collection consent not granted for this account")
    if module_id not in VALID_MODULE_IDS:
        raise HTTPException(400, f"module_id must be one of {sorted(VALID_MODULE_IDS)}")
    if outcome not in VALID_OUTCOMES:
        raise HTTPException(400, f"outcome must be one of {sorted(VALID_OUTCOMES)}")
    if file.content_type not in ("image/jpeg", "image/jpg", "image/png"):
        raise HTTPException(400, "file must be image/jpeg or image/png")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(400, "Uploaded file is empty")
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File exceeds {MAX_UPLOAD_BYTES} byte limit")

    service = TrainingDataService(db)
    try:
        sample = await service.upload_sample(
            user_id=current_user.id,
            module_id=module_id,
            outcome=outcome,
            confidence_score=confidence_score,
            image_bytes=image_bytes,
            content_type=file.content_type,
        )
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc

    await db.commit()
    return TrainingSampleUploadResponse(
        sample_id=sample.id,
        hf_dataset_path=sample.hf_dataset_path,
        uploaded_at=sample.uploaded_at,
    )
