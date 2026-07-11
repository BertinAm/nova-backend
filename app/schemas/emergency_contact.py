"""Request/response schemas for the emergency contact endpoint (FR-06-04)."""
import re

from pydantic import BaseModel, Field, field_validator

# E.164-ish international phone format, permissive enough for Cameroonian
# numbers (+237...) and general international numbers.
PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{6,14}$")


class EmergencyContactRequest(BaseModel):
    contact_name: str = Field(min_length=1, max_length=100)
    phone_number: str = Field(min_length=7, max_length=20)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        cleaned = value.replace(" ", "").replace("-", "")
        if not PHONE_PATTERN.match(cleaned):
            raise ValueError("phone_number must be a valid international phone number")
        return cleaned


class EmergencyContactResponse(BaseModel):
    id: str
    contact_name: str
    phone_number: str
