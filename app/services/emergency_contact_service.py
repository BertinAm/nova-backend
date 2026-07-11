"""Business logic for the single emergency contact per user (FR-06-04).

The phone number is encrypted at rest with AES-256/Fernet (NFR-27 scope
extended to PII) and only decrypted when returned to its owning user or
read for SMS dispatch.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import audit_log
from app.models.emergency_contact import EmergencyContact
from app.security.crypto import decrypt_str, encrypt_str


class EmergencyContactService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, user_id: str) -> EmergencyContact | None:
        result = await self.db.execute(
            select(EmergencyContact).where(EmergencyContact.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, user_id: str, contact_name: str, phone_number: str) -> EmergencyContact:
        """Create or replace the user's single emergency contact.

        One-to-one relationship (DB design doc 2.6 / NFR): re-submitting
        overwrites the existing contact rather than creating a second row.
        """
        existing = await self.get(user_id)
        encrypted_phone = encrypt_str(phone_number)

        if existing is not None:
            existing.contact_name = contact_name
            existing.phone_encrypted = encrypted_phone
            await self.db.flush()
            audit_log("emergency_contact.updated", user_id=user_id, contact_id=existing.id)
            return existing

        contact = EmergencyContact(
            user_id=user_id,
            contact_name=contact_name,
            phone_encrypted=encrypted_phone,
        )
        self.db.add(contact)
        await self.db.flush()
        audit_log("emergency_contact.created", user_id=user_id, contact_id=contact.id)
        return contact

    async def delete(self, user_id: str) -> bool:
        existing = await self.get(user_id)
        if existing is None:
            return False
        await self.db.delete(existing)
        audit_log("emergency_contact.deleted", user_id=user_id, contact_id=existing.id)
        return True

    @staticmethod
    def decrypt_phone(contact: EmergencyContact) -> str:
        return decrypt_str(contact.phone_encrypted)
