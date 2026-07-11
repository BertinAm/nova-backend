"""Usage event and feedback batch sync from the mobile offline queue."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.rate_limit import limiter
from app.schemas.logs import FeedbackBatch, SyncResponse, UsageEventBatch
from app.services.log_service import LogService

router = APIRouter(prefix="/logs", tags=["Usage Logs"])


@router.post("/sync", response_model=SyncResponse)
@limiter.limit("30/minute")
async def sync_logs(
    request: Request,
    batch: UsageEventBatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Batch-insert usage events from the device's offline queue. Idempotent."""
    service = LogService(db)
    inserted, total = await service.batch_sync_events(batch, current_user.id)
    return SyncResponse(inserted=inserted, total=total)


@router.post("/feedback/sync", response_model=SyncResponse)
@limiter.limit("30/minute")
async def sync_feedback(
    request: Request,
    batch: FeedbackBatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Batch-insert user feedback (good/bad) records. Idempotent."""
    service = LogService(db)
    inserted, total = await service.batch_sync_feedback(batch)
    return SyncResponse(inserted=inserted, total=total)
