"""FastAPI application factory for the NOVA backend."""
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.exceptions import register_exception_handlers
from app.logging_config import configure_logging, get_logger
from app.middleware import RequestLoggingMiddleware, SecurityHeadersMiddleware
from app.ml.scene_describer import SceneDescriber
from app.rate_limit import limiter
from app.routers import (
    admin,
    auth,
    emergency_contact,
    faces,
    logs,
    model_registry,
    scene,
    training_data,
)

STATIC_DIR = Path(__file__).parent / "static"

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting NOVA backend (environment=%s)", settings.ENVIRONMENT)
    if settings.USE_LOCAL_VLM:
        logger.info("Loading local VLM for scene description...")
        await SceneDescriber.load()
    logger.info("NOVA backend ready.")
    yield
    logger.info("Shutting down NOVA backend.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="NOVA Backend API",
        description="Navigational Object and Voice Assistant — Backend Services",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    register_exception_handlers(app)

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(scene.router)
    app.include_router(faces.router)
    app.include_router(logs.router)
    app.include_router(model_registry.router)
    app.include_router(emergency_contact.router)
    app.include_router(admin.router)
    app.include_router(training_data.router)

    @app.get("/admin", tags=["Admin Dashboard"], include_in_schema=False)
    async def admin_dashboard():
        """Serves the operator dashboard SPA. The page itself calls the
        JSON /admin/* API (all operator-gated) — this route serves static
        HTML/JS only and requires no auth on its own."""
        return FileResponse(STATIC_DIR / "admin.html")

    @app.get("/health", tags=["Health"])
    async def health(response: Response, db: AsyncSession = Depends(get_db)):
        """Liveness + readiness probe.

        Reports ``ok`` only if the database is actually reachable; a
        misconfigured or unreachable DB returns 503 so orchestrators
        (Docker healthcheck, Kubernetes, load balancer) stop routing
        traffic to this instance instead of serving 500s.
        """
        db_ok = True
        try:
            await db.execute(text("SELECT 1"))
        except Exception:
            logger.exception("Health check: database is unreachable")
            db_ok = False

        if not db_ok:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return {
            "status": "ok" if db_ok else "degraded",
            "service": "NOVA Backend",
            "checks": {"database": "ok" if db_ok else "unreachable"},
        }

    return app


app = create_app()
