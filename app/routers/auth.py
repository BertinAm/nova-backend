"""Authentication endpoints: register, login, refresh."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.rate_limit import limiter
from app.schemas.auth import (
    RefreshRequest,
    TokenResponse,
    UserRegisterRequest,
    UserRegisterResponse,
)
from app.security.jwt import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token_of_type,
)
from app.services.auth_service import AuthService, EmailAlreadyRegisteredError

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserRegisterResponse, status_code=201)
@limiter.limit("10/minute")
async def register(
    request: Request,
    body: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new NOVA user account."""
    service = AuthService(db)
    try:
        user = await service.register(body.email, body.password, body.preferred_language)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(status_code=409, detail="Email already registered") from exc
    return UserRegisterResponse(
        id=user.id, email=user.email, preferred_language=user.preferred_language
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("20/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email/password and receive JWT access + refresh tokens."""
    service = AuthService(db)
    user = await service.authenticate(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh_token(request: Request, body: RefreshRequest):
    """Exchange a valid, unexpired refresh token for a new token pair."""
    try:
        payload = decode_token_of_type(body.refresh_token, "refresh")
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc

    user_id = payload["sub"]
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )
