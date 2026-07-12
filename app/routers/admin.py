"""Operator admin API: platform stats, user management, model registry
management, and usage/feedback analytics for the NOVA dashboard.

Every route requires an operator account (``User.is_operator``). This
router only reads/writes existing tables — it introduces no new schema.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_operator
from app.logging_config import audit_log
from app.models.emergency_contact import EmergencyContact
from app.models.enrolled_face import EnrolledFace
from app.models.model_registry import ModelRegistry
from app.models.usage_event import UsageEvent
from app.models.user import User
from app.models.user_feedback import UserFeedback
from app.schemas.admin import (
    AdminModelSummary,
    AdminUserListResponse,
    AdminUserSummary,
    DailyEventCount,
    DashboardStats,
    ModuleUsageStat,
    RecentEventSummary,
    SetActiveRequest,
    SetOperatorRequest,
)

router = APIRouter(
    prefix="/admin", tags=["Admin Dashboard"], dependencies=[Depends(get_current_operator)]
)


# ── Overview ────────────────────────────────────────────────────────────
@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    # event_timestamp is stored as a naive DateTime column (UTC implied);
    # asyncpg rejects binding a tz-aware datetime against it, so drop the
    # tzinfo after computing the cutoff in UTC.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    active_users = (
        await db.execute(select(func.count(User.id)).where(User.is_active.is_(True)))
    ).scalar_one()
    operator_users = (
        await db.execute(select(func.count(User.id)).where(User.is_operator.is_(True)))
    ).scalar_one()
    total_faces = (await db.execute(select(func.count(EnrolledFace.id)))).scalar_one()
    total_events = (await db.execute(select(func.count(UsageEvent.id)))).scalar_one()
    total_feedback = (await db.execute(select(func.count(UserFeedback.id)))).scalar_one()
    positive_feedback = (
        await db.execute(select(func.count(UserFeedback.id)).where(UserFeedback.is_positive.is_(True)))
    ).scalar_one()
    events_24h = (
        await db.execute(
            select(func.count(UsageEvent.id)).where(UsageEvent.event_timestamp >= day_ago)
        )
    ).scalar_one()
    events_7d = (
        await db.execute(
            select(func.count(UsageEvent.id)).where(UsageEvent.event_timestamp >= week_ago)
        )
    ).scalar_one()
    active_modules = (
        await db.execute(
            select(ModelRegistry.module_id).where(ModelRegistry.is_active.is_(True))
        )
    ).scalars().all()

    return DashboardStats(
        total_users=total_users,
        active_users=active_users,
        operator_users=operator_users,
        total_enrolled_faces=total_faces,
        total_usage_events=total_events,
        total_feedback=total_feedback,
        positive_feedback_pct=(
            round(100 * positive_feedback / total_feedback, 1) if total_feedback else None
        ),
        events_last_24h=events_24h,
        events_last_7d=events_7d,
        active_model_count=len(active_modules),
        module_ids_with_active_model=sorted(active_modules),
    )


@router.get("/stats/by-module", response_model=list[ModuleUsageStat])
async def get_module_usage_stats(db: AsyncSession = Depends(get_db)):
    """Per-module breakdown: outcome counts, average confidence, feedback."""
    rows = (
        await db.execute(
            select(
                UsageEvent.module_id,
                func.count(UsageEvent.id).label("total"),
                func.sum(case((UsageEvent.outcome == "success", 1), else_=0)).label("success"),
                func.sum(case((UsageEvent.outcome == "error", 1), else_=0)).label("error"),
                func.sum(case((UsageEvent.outcome == "no_detection", 1), else_=0)).label("no_detection"),
                func.sum(case((UsageEvent.outcome == "low_confidence", 1), else_=0)).label("low_confidence"),
                func.sum(case((UsageEvent.outcome == "offline_skip", 1), else_=0)).label("offline_skip"),
                func.avg(UsageEvent.confidence_score).label("avg_conf"),
            ).group_by(UsageEvent.module_id)
        )
    ).all()

    stats = []
    for row in rows:
        fb = (
            await db.execute(
                select(
                    func.sum(case((UserFeedback.is_positive.is_(True), 1), else_=0)),
                    func.sum(case((UserFeedback.is_positive.is_(False), 1), else_=0)),
                )
                .join(UsageEvent, UserFeedback.event_id == UsageEvent.id)
                .where(UsageEvent.module_id == row.module_id)
            )
        ).one()
        stats.append(
            ModuleUsageStat(
                module_id=row.module_id,
                total_events=row.total,
                success_count=row.success or 0,
                error_count=row.error or 0,
                no_detection_count=row.no_detection or 0,
                low_confidence_count=row.low_confidence or 0,
                offline_skip_count=row.offline_skip or 0,
                avg_confidence=round(row.avg_conf, 4) if row.avg_conf is not None else None,
                positive_feedback=fb[0] or 0,
                negative_feedback=fb[1] or 0,
            )
        )
    return sorted(stats, key=lambda s: s.module_id)


@router.get("/stats/daily-events", response_model=list[DailyEventCount])
async def get_daily_event_counts(days: int = 14, db: AsyncSession = Depends(get_db)):
    """Event volume per day for the last N days — feeds the dashboard chart."""
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    day_expr = func.date(UsageEvent.event_timestamp)
    rows = (
        await db.execute(
            select(day_expr.label("day"), func.count(UsageEvent.id))
            .where(UsageEvent.event_timestamp >= since)
            .group_by(day_expr)
            .order_by(day_expr)
        )
    ).all()
    return [DailyEventCount(date=str(r[0]), count=r[1]) for r in rows]


@router.get("/events/recent", response_model=list[RecentEventSummary])
async def get_recent_events(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Latest usage events across all users, with feedback if present —
    the operator's live activity feed."""
    limit = min(limit, 200)
    rows = (
        await db.execute(
            select(UsageEvent, User.email, UserFeedback.is_positive)
            .outerjoin(User, UsageEvent.user_id == User.id)
            .outerjoin(UserFeedback, UserFeedback.event_id == UsageEvent.id)
            .order_by(UsageEvent.event_timestamp.desc())
            .limit(limit)
        )
    ).all()
    return [
        RecentEventSummary(
            id=event.id,
            user_id=event.user_id,
            user_email=email,
            module_id=event.module_id,
            event_timestamp=event.event_timestamp,
            outcome=event.outcome,
            confidence_score=event.confidence_score,
            feedback_positive=is_positive,
        )
        for event, email, is_positive in rows
    ]


# ── User management ─────────────────────────────────────────────────────
@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    base_query = select(User)
    if search:
        base_query = base_query.where(User.email.ilike(f"%{search}%"))

    total = (
        await db.execute(select(func.count()).select_from(base_query.subquery()))
    ).scalar_one()

    rows = (
        await db.execute(
            base_query.order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    summaries = []
    for user in rows:
        face_count = (
            await db.execute(
                select(func.count(EnrolledFace.id)).where(EnrolledFace.user_id == user.id)
            )
        ).scalar_one()
        event_count = (
            await db.execute(
                select(func.count(UsageEvent.id)).where(UsageEvent.user_id == user.id)
            )
        ).scalar_one()
        has_contact = (
            await db.execute(
                select(func.count(EmergencyContact.id)).where(EmergencyContact.user_id == user.id)
            )
        ).scalar_one() > 0
        summaries.append(
            AdminUserSummary(
                id=user.id,
                email=user.email,
                preferred_language=user.preferred_language,
                is_active=user.is_active,
                is_operator=user.is_operator,
                created_at=user.created_at,
                enrolled_face_count=face_count,
                usage_event_count=event_count,
                has_emergency_contact=has_contact,
            )
        )

    return AdminUserListResponse(total=total, page=page, page_size=page_size, users=summaries)


@router.patch("/users/{user_id}/operator", response_model=AdminUserSummary)
async def set_user_operator_status(
    user_id: str,
    body: SetOperatorRequest,
    db: AsyncSession = Depends(get_db),
    current_operator: User = Depends(get_current_operator),
):
    """Grant or revoke operator privileges. An operator cannot demote
    themselves — prevents accidentally locking out the last operator."""
    if user_id == current_operator.id and not body.is_operator:
        raise HTTPException(400, "Cannot revoke your own operator privileges")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    user.is_operator = body.is_operator
    await db.flush()
    await db.commit()
    audit_log(
        "admin.user_operator_changed",
        target_user_id=user_id,
        new_value=body.is_operator,
        changed_by=current_operator.id,
    )
    return AdminUserSummary(
        id=user.id,
        email=user.email,
        preferred_language=user.preferred_language,
        is_active=user.is_active,
        is_operator=user.is_operator,
        created_at=user.created_at,
        enrolled_face_count=0,
        usage_event_count=0,
        has_emergency_contact=False,
    )


@router.patch("/users/{user_id}/active")
async def set_user_active_status(
    user_id: str,
    body: SetActiveRequest,
    db: AsyncSession = Depends(get_db),
    current_operator: User = Depends(get_current_operator),
):
    """Suspend (soft-disable) or reactivate a user account."""
    if user_id == current_operator.id and not body.is_active:
        raise HTTPException(400, "Cannot deactivate your own account")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    user.is_active = body.is_active
    await db.commit()
    audit_log(
        "admin.user_active_changed",
        target_user_id=user_id,
        new_value=body.is_active,
        changed_by=current_operator.id,
    )
    return {"id": user.id, "is_active": user.is_active}


# ── Model registry management ───────────────────────────────────────────
@router.get("/models", response_model=list[AdminModelSummary])
async def list_all_models(db: AsyncSession = Depends(get_db)):
    """Every registered model version across all modules, newest first."""
    rows = (
        await db.execute(select(ModelRegistry).order_by(ModelRegistry.uploaded_at.desc()))
    ).scalars().all()
    return [
        AdminModelSummary(
            id=m.id, module_id=m.module_id, version=m.version, filename=m.filename,
            checksum=m.checksum, hf_repo_url=m.hf_repo_url, is_active=m.is_active,
            uploaded_at=m.uploaded_at, notes=m.notes,
        )
        for m in rows
    ]


@router.post("/models/{model_id}/activate")
async def activate_model_version(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    current_operator: User = Depends(get_current_operator),
):
    """Roll forward (or back) to a specific version for its module —
    deactivates any other version of the same module_id."""
    model = await db.get(ModelRegistry, model_id)
    if not model:
        raise HTTPException(404, "Model version not found")

    others = (
        await db.execute(
            select(ModelRegistry).where(
                ModelRegistry.module_id == model.module_id, ModelRegistry.id != model.id
            )
        )
    ).scalars().all()
    for other in others:
        other.is_active = False
    model.is_active = True
    await db.commit()
    audit_log(
        "admin.model_activated",
        module_id=model.module_id,
        version=model.version,
        changed_by=current_operator.id,
    )
    return {"module_id": model.module_id, "active_version": model.version}


@router.delete("/models/{model_id}")
async def delete_model_version(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    current_operator: User = Depends(get_current_operator),
):
    """Remove a model version's registry entry (e.g. a bad publish).
    Does not delete the underlying file on disk/HF — registry only."""
    model = await db.get(ModelRegistry, model_id)
    if not model:
        raise HTTPException(404, "Model version not found")
    if model.is_active:
        raise HTTPException(400, "Cannot delete the active version — activate another version first")

    await db.delete(model)
    await db.commit()
    audit_log(
        "admin.model_deleted",
        module_id=model.module_id,
        version=model.version,
        changed_by=current_operator.id,
    )
