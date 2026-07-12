"""Request/response schemas for opt-in training-data collection."""
from datetime import datetime

from pydantic import BaseModel


class ConsentRequest(BaseModel):
    consent: bool


class ConsentResponse(BaseModel):
    data_collection_consent: bool


class TrainingSampleUploadResponse(BaseModel):
    sample_id: str
    hf_dataset_path: str
    uploaded_at: datetime
