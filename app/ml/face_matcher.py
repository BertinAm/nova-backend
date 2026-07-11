"""InsightFace (ArcFace) wrapper for server-side face matching (MOD-05).

The model is loaded lazily on first use and reused across requests; loading
``FaceAnalysis`` per-request would add hundreds of milliseconds of latency.
"""
import asyncio
from typing import Any

import numpy as np

from app.logging_config import get_logger

logger = get_logger(__name__)


class NoFaceDetectedError(ValueError):
    pass


class FaceMatcher:
    _app: Any = None
    _lock = asyncio.Lock()

    @classmethod
    async def _get_app(cls):
        if cls._app is None:
            async with cls._lock:
                if cls._app is None:
                    cls._app = await asyncio.get_event_loop().run_in_executor(None, cls._build_app)
        return cls._app

    @staticmethod
    def _build_app():
        import insightface

        app = insightface.app.FaceAnalysis(name="buffalo_sc")
        app.prepare(ctx_id=-1)  # CPU inference — no GPU assumed on the reference deployment
        return app

    @classmethod
    async def extract_embedding(cls, image_bytes: bytes) -> np.ndarray:
        app = await cls._get_app()
        return await asyncio.get_event_loop().run_in_executor(
            None, cls._extract_embedding_sync, app, image_bytes
        )

    @staticmethod
    def _extract_embedding_sync(app, image_bytes: bytes) -> np.ndarray:
        import cv2

        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Invalid image data")

        faces = app.get(img)
        if not faces:
            raise NoFaceDetectedError("No face detected in image")
        return faces[0].normed_embedding.astype(np.float32)

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8
        return float(np.dot(a, b) / denom)
