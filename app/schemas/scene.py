"""Request/response schemas for scene description."""
from pydantic import BaseModel, Field


class SceneDescribeResponse(BaseModel):
    description: str = Field(max_length=600)
