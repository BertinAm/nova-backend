"""Shared slowapi rate limiter instance (NFR-29: 60 req/min per user).

Backed by Redis so limits are enforced consistently across the multiple
Gunicorn worker processes specified in the Dockerfile — an in-memory
limiter would let each worker process its own independent quota, letting
a client effectively multiply its allowed request rate by the worker
count.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.RATE_LIMIT_STORAGE_URI,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
)
