"""Password hashing helpers (bcrypt, cost factor 12 per NFR-30)."""
from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12)


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _pwd_context.verify(plain_password, password_hash)
