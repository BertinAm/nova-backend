"""Scene description endpoint (MOD-03). Cloud-dependent, transient processing only."""
import io

import PIL.Image as PILImage
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.rate_limit import limiter
from app.schemas.scene import SceneDescribeResponse
from app.services.scene_service import SceneService

router = APIRouter(prefix="/scene", tags=["Scene Description"])

MAX_IMAGE_SIZE = 512 * 1024  # 512 KB, per FR-03-03
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png"}


@router.post("/describe", response_model=SceneDescribeResponse)
@limiter.limit("20/minute")
async def describe_scene(
    request: Request,
    image: UploadFile = File(..., description="JPEG or PNG image, max 512KB"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Accept a still frame from the NOVA mobile app and return a natural
    language scene description. The image is processed transiently and is
    never written to disk or the database (FR-03-08, NFR-28).
    """
    if image.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(400, "Image must be JPEG or PNG")

    image_bytes = await image.read()
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(413, f"Image exceeds {MAX_IMAGE_SIZE // 1024}KB limit")

    try:
        PILImage.open(io.BytesIO(image_bytes)).verify()
    except Exception as exc:
        raise HTTPException(400, "Invalid image data") from exc

    service = SceneService()
    try:
        description = await service.describe(image_bytes, current_user.id)
    except Exception as exc:
        raise HTTPException(503, "Scene description is unavailable right now") from exc

    return SceneDescribeResponse(description=description)
