"""Request/response schemas for the model registry router."""
from datetime import datetime

from pydantic import BaseModel


class ModelVersionResponse(BaseModel):
    model_id: str
    version: str
    filename: str
    checksum: str
    download_url: str
    hf_repo_url: str | None = None


class ModelRegisterResponse(BaseModel):
    model_id: str
    module_id: str
    version: str
    filename: str
    checksum: str
    is_active: bool
    uploaded_at: datetime
