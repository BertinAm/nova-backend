"""Business logic for the OTA model registry (FR-06-07, FR-06-09)."""
import hashlib

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import audit_log
from app.models.model_registry import ModelRegistry


class ModelService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_latest_active(self, module_id: str) -> ModelRegistry | None:
        result = await self.db.execute(
            select(ModelRegistry)
            .where(ModelRegistry.module_id == module_id, ModelRegistry.is_active.is_(True))
            .order_by(ModelRegistry.uploaded_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def register_model(
        self,
        module_id: str,
        version: str,
        filename: str,
        file_bytes: bytes,
        hf_repo_url: str | None,
        notes: str | None,
        activate: bool = True,
    ) -> ModelRegistry:
        checksum = hashlib.sha256(file_bytes).hexdigest()

        if activate:
            # Only one active model per module at a time.
            await self.db.execute(
                update(ModelRegistry)
                .where(ModelRegistry.module_id == module_id)
                .values(is_active=False)
            )

        model = ModelRegistry(
            module_id=module_id,
            version=version,
            filename=filename,
            checksum=checksum,
            hf_repo_url=hf_repo_url,
            notes=notes,
            is_active=activate,
            file_data=file_bytes,
        )
        self.db.add(model)
        await self.db.flush()

        audit_log(
            "model.registered",
            module_id=module_id,
            version=version,
            checksum=checksum,
            is_active=activate,
        )
        return model
