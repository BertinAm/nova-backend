"""Global exception handlers producing a consistent JSON error envelope.

Every error response (validation, HTTP, or unhandled) takes the shape:

    {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "...",
            "request_id": "...",
            "details": [...]   # optional, e.g. per-field validation errors
        }
    }

``request_id`` matches the ``X-Request-ID`` response header set by
``RequestLoggingMiddleware`` so a client-reported error can be correlated
with server logs.
"""
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_config import get_logger

logger = get_logger("nova.errors")

# Maps common HTTP status codes to a stable machine-readable error code.
_STATUS_CODE_NAMES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def _error_envelope(request: Request, code: str, message: str, details: list | None = None) -> dict:
    request_id = getattr(request.state, "request_id", None)
    body = {"error": {"code": code, "message": message, "request_id": request_id}}
    if details:
        body["error"]["details"] = details
    return body


async def http_exception_handler(request: Request, exc: HTTPException | StarletteHTTPException):
    code = _STATUS_CODE_NAMES.get(exc.status_code, "HTTP_ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_envelope(request, code, str(exc.detail)),
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = [
        {"field": ".".join(str(p) for p in err["loc"]), "message": err["msg"]}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=_error_envelope(
            request, "VALIDATION_ERROR", "Request validation failed", details
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
        extra={"extra_fields": {"request_id": request_id}},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_envelope(
            request, "INTERNAL_ERROR", "An unexpected error occurred. Please try again."
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
