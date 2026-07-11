"""Structured logging setup.

Two loggers are configured:

- ``nova`` — general application logs (requests, errors, ML timing).
- ``nova.audit`` — security-relevant events (auth attempts, face enrolment/
  deletion, model installs). Audit records are always emitted as single-line
  JSON so they can be shipped to a SIEM or log aggregator without parsing
  ambiguity, and they never include secrets, passwords, tokens, or raw
  biometric data.
"""
import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.config import get_settings

settings = get_settings()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger("nova")
    root.setLevel(settings.LOG_LEVEL)
    root.handlers = [handler]
    root.propagate = False

    audit = logging.getLogger("nova.audit")
    audit.setLevel(logging.INFO)
    audit.handlers = [handler]
    audit.propagate = False

    # Quiet noisy third-party loggers in production
    logging.getLogger("uvicorn.access").setLevel(
        logging.WARNING if settings.is_production else logging.INFO
    )


def get_logger(name: str = "nova") -> logging.Logger:
    return logging.getLogger(name)


def audit_log(event: str, **fields: Any) -> None:
    """Record a security-relevant event to the audit log.

    Never pass raw passwords, tokens, face images, or embedding vectors as
    fields — only identifiers (user_id, event type, outcome).
    """
    logger = logging.getLogger("nova.audit")
    logger.info(event, extra={"extra_fields": {"event": event, **fields}})
