"""Business logic for opt-in training-data collection.

Images never touch Render's disk — they're streamed straight to a
Hugging Face dataset repo, and only lightweight provenance metadata
(module, outcome, confidence, HF path) is kept in Postgres.
"""
import io
import uuid

from app.config import get_settings
from app.logging_config import audit_log
from app.models.training_sample import TrainingSample
from sqlalchemy.ext.asyncio import AsyncSession

settings = get_settings()

_repo_ensured = False


def _ensure_repo() -> None:
    """Create the HF dataset repo on first use. Cheap no-op after that —
    HfApi.create_repo(exist_ok=True) is idempotent, but this avoids one
    network round-trip per upload."""
    global _repo_ensured
    if _repo_ensured:
        return
    from huggingface_hub import HfApi

    HfApi(token=settings.HF_TOKEN).create_repo(
        settings.TRAINING_DATA_HF_REPO, repo_type="dataset", exist_ok=True, private=True
    )
    _repo_ensured = True


class TrainingDataService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upload_sample(
        self,
        user_id: str | None,
        module_id: str,
        outcome: str,
        confidence_score: float | None,
        image_bytes: bytes,
        content_type: str,
    ) -> TrainingSample:
        if not settings.HF_TOKEN:
            raise RuntimeError("HF_TOKEN not configured — training-data uploads are disabled")

        ext = "jpg" if "jpeg" in content_type or "jpg" in content_type else "png"
        sample_id = str(uuid.uuid4())
        # Path groups by module/outcome so a retraining pass can pull just
        # the hard examples for one module (e.g. all MOD-04 low_confidence
        # frames) without downloading the whole dataset repo.
        repo_path = f"{module_id}/{outcome}/{sample_id}.{ext}"

        _ensure_repo()
        from huggingface_hub import HfApi

        HfApi(token=settings.HF_TOKEN).upload_file(
            path_or_fileobj=io.BytesIO(image_bytes),
            path_in_repo=repo_path,
            repo_id=settings.TRAINING_DATA_HF_REPO,
            repo_type="dataset",
            commit_message=f"Add {module_id}/{outcome} sample",
        )

        sample = TrainingSample(
            id=sample_id,
            user_id=user_id,
            module_id=module_id,
            outcome=outcome,
            confidence_score=confidence_score,
            hf_dataset_path=repo_path,
        )
        self.db.add(sample)
        await self.db.flush()

        audit_log(
            "training_data.sample_uploaded",
            module_id=module_id,
            outcome=outcome,
            hf_dataset_path=repo_path,
        )
        return sample
