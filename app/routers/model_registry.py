"""OTA model registry: lookup, download, and upload of TFLite models."""
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_operator, get_current_user
from app.models.user import User
from app.schemas.models import ModelRegisterResponse, ModelVersionResponse
from app.services.model_service import ModelService

router = APIRouter(prefix="/models", tags=["Model Registry"])
settings = get_settings()

VALID_MODULE_IDS = {"MOD-01", "MOD-04", "MOD-05-detect", "MOD-05-embed"}


@router.get("/latest/{module_id}", response_model=ModelVersionResponse)
async def get_latest_model(
    module_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return metadata for the latest active model for a module (FR-06-07).

    "MOD-05" alone means face embedding to every caller outside this
    codebase — the split into MOD-05-detect/MOD-05-embed is an internal
    registry detail. Treat a bare "MOD-05" request as MOD-05-embed so a
    client doesn't need to know that split to get the right model.
    """
    if module_id == "MOD-05":
        module_id = "MOD-05-embed"
    if module_id == "MOD-05-detect":
        raise HTTPException(
            404,
            "MOD-05-detect has no backend model — face detection uses a stock "
            "bundled model (e.g. MediaPipe BlazeFace) on-device, not an OTA "
            "download. Request MOD-05-embed for the face embedding model.",
        )

    service = ModelService(db)
    model = await service.get_latest_active(module_id)
    if not model:
        raise HTTPException(404, f"No active model found for module: {module_id}")
    return ModelVersionResponse(
        model_id=model.id,
        version=model.version,
        filename=model.filename,
        checksum=model.checksum,
        download_url=f"/models/download/{model.id}",
        hf_repo_url=model.hf_repo_url,
    )


@router.get("/download/{model_id}")
async def download_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Stream the TFLite model file. The mobile app verifies the SHA-256
    checksum (from /models/latest) before installing — FR-06-09."""
    from app.models.model_registry import ModelRegistry

    model = await db.get(ModelRegistry, model_id)
    if not model:
        raise HTTPException(404, "Model not found")

    file_path = os.path.join(settings.MODEL_STORAGE_PATH, model.filename)
    if not os.path.exists(file_path):
        raise HTTPException(404, "Model file not found on server")

    return FileResponse(file_path, media_type="application/octet-stream", filename=model.filename)


@router.post("/register", response_model=ModelRegisterResponse, status_code=201)
async def register_model(
    module_id: str = Form(...),
    version: str = Form(...),
    hf_repo_url: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    activate: bool = Form(default=True),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_operator),
):
    """
    Upload and register a new TFLite model version. Saves the file to
    ``MODEL_STORAGE_PATH``, computes its SHA-256 checksum, and (by default)
    deactivates any previously active model for the same module.

    Restricted to operator/admin accounts (``User.is_operator``) — regular
    BVI user accounts cannot push new models.
    """
    if module_id not in VALID_MODULE_IDS:
        raise HTTPException(400, f"module_id must be one of {VALID_MODULE_IDS}")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(400, "Uploaded file is empty")

    filename = f"{module_id}_{version}.tflite"
    os.makedirs(settings.MODEL_STORAGE_PATH, exist_ok=True)
    file_path = os.path.join(settings.MODEL_STORAGE_PATH, filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    service = ModelService(db)
    try:
        model = await service.register_model(
            module_id=module_id,
            version=version,
            filename=filename,
            file_bytes=file_bytes,
            hf_repo_url=hf_repo_url,
            notes=notes,
            activate=activate,
        )
    except Exception as exc:
        os.remove(file_path)
        raise HTTPException(409, "Failed to register model (duplicate module/version?)") from exc

    await db.commit()
    return ModelRegisterResponse(
        model_id=model.id,
        module_id=model.module_id,
        version=model.version,
        filename=model.filename,
        checksum=model.checksum,
        is_active=model.is_active,
        uploaded_at=model.uploaded_at,
    )
