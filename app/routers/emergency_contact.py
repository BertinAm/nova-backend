"""Emergency contact CRUD (FR-06-04: 'Call for help' / 'Send my location').

Each user has at most one emergency contact (one-to-one, see DB design
doc section 2.6). The phone number is never returned in plaintext to
anyone but the owning, authenticated user.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.emergency_contact import EmergencyContactRequest, EmergencyContactResponse
from app.services.emergency_contact_service import EmergencyContactService

router = APIRouter(prefix="/emergency-contact", tags=["Emergency Contact"])


def _to_response(contact, service: EmergencyContactService) -> EmergencyContactResponse:
    return EmergencyContactResponse(
        id=contact.id,
        contact_name=contact.contact_name,
        phone_number=service.decrypt_phone(contact),
    )


@router.get("/", response_model=EmergencyContactResponse)
async def get_emergency_contact(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's emergency contact, if one is set."""
    service = EmergencyContactService(db)
    contact = await service.get(current_user.id)
    if contact is None:
        raise HTTPException(404, "No emergency contact set")
    return _to_response(contact, service)


@router.put("/", response_model=EmergencyContactResponse)
async def set_emergency_contact(
    body: EmergencyContactRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or replace the current user's emergency contact."""
    service = EmergencyContactService(db)
    contact = await service.upsert(current_user.id, body.contact_name, body.phone_number)
    await db.commit()
    return _to_response(contact, service)


@router.delete("/", status_code=204)
async def delete_emergency_contact(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove the current user's emergency contact."""
    service = EmergencyContactService(db)
    deleted = await service.delete(current_user.id)
    if not deleted:
        raise HTTPException(404, "No emergency contact set")
    await db.commit()
