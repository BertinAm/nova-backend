"""Business logic for registration and authentication."""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import audit_log, get_logger
from app.models.user import User
from app.security.hashing import hash_password, verify_password

logger = get_logger(__name__)


class EmailAlreadyRegisteredError(ValueError):
    pass


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, email: str, password: str, preferred_language: str) -> User:
        existing = await self.db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none() is not None:
            raise EmailAlreadyRegisteredError(f"Email already registered: {email}")

        user = User(
            email=email,
            password_hash=hash_password(password),
            preferred_language=preferred_language,
        )
        self.db.add(user)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            raise EmailAlreadyRegisteredError(f"Email already registered: {email}") from exc

        audit_log("user.registered", user_id=user.id)
        return user

    async def authenticate(self, email: str, password: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None or not user.is_active:
            audit_log("auth.login_failed", email=email, reason="user_not_found_or_inactive")
            return None

        if not verify_password(password, user.password_hash):
            audit_log("auth.login_failed", user_id=user.id, reason="bad_password")
            return None

        audit_log("auth.login_success", user_id=user.id)
        return user

    async def get_user_by_id(self, user_id: str) -> User | None:
        return await self.db.get(User, user_id)
