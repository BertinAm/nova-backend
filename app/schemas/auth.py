"""Request/response schemas for the authentication router."""
from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    preferred_language: str = Field(default="en-CM", max_length=10)

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if value.isnumeric() or value.isalpha():
            raise ValueError("Password must contain a mix of letters and numbers")
        return value

    @field_validator("preferred_language")
    @classmethod
    def language_allowed(cls, value: str) -> str:
        allowed = {"en-CM", "fr-CM"}
        if value not in allowed:
            raise ValueError(f"preferred_language must be one of {allowed}")
        return value


class UserRegisterResponse(BaseModel):
    id: str
    email: EmailStr
    preferred_language: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
