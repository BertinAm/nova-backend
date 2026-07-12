"""Vision-language model wrapper for scene description (MOD-03).

Supports two backends, selected via ``USE_LOCAL_VLM``:

- Local: BLIP-2, loaded once at app startup and run in a thread executor
  (PyTorch inference is blocking/CPU-bound, so it must not run on the
  asyncio event loop directly).
- Cloud: an external vision-capable chat completion API.
"""
import asyncio
import base64
import io

from PIL import Image

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_PROMPT = "Describe this scene in one sentence for a blind person:"


class SceneDescriber:
    _processor = None
    _model = None
    _loaded = False

    @classmethod
    async def load(cls) -> None:
        """Load the local VLM weights. Called once from the app lifespan."""
        settings = get_settings()
        if settings.USE_LOCAL_VLM:
            await asyncio.get_event_loop().run_in_executor(None, cls._load_blip2)
        cls._loaded = True
        logger.info("SceneDescriber loaded (local_vlm=%s)", settings.USE_LOCAL_VLM)

    @classmethod
    def _load_blip2(cls) -> None:
        import torch
        from transformers import Blip2ForConditionalGeneration, Blip2Processor

        settings = get_settings()
        cls._processor = Blip2Processor.from_pretrained(settings.VLM_MODEL_NAME)
        cls._model = Blip2ForConditionalGeneration.from_pretrained(
            settings.VLM_MODEL_NAME,
            torch_dtype=torch.float16,
            device_map="auto",
        )

    @classmethod
    async def describe(cls, image_bytes: bytes) -> str:
        settings = get_settings()
        if settings.USE_LOCAL_VLM:
            return await asyncio.get_event_loop().run_in_executor(
                None, cls._describe_local, image_bytes
            )
        return await cls._describe_cloud(image_bytes)

    @classmethod
    def _describe_local(cls, image_bytes: bytes) -> str:
        import torch

        if cls._model is None or cls._processor is None:
            raise RuntimeError("SceneDescriber.load() must be called before describe()")

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        inputs = cls._processor(images=image, text=DEFAULT_PROMPT, return_tensors="pt").to(
            device, torch.float16
        )
        generated_ids = cls._model.generate(**inputs, max_new_tokens=60)
        return cls._processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()

    @classmethod
    async def _describe_cloud(cls, image_bytes: bytes) -> str:
        import httpx

        settings = get_settings()
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is required when USE_LOCAL_VLM=False")

        b64 = base64.b64encode(image_bytes).decode()
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Describe this scene briefly for a blind person (max 60 words).",
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                                },
                            ],
                        }
                    ],
                    "max_tokens": 80,
                },
            )
            response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
