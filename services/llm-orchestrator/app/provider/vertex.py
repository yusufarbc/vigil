"""
Vertex AI (Gemini) LLM provider.
Uses google-cloud-aiplatform SDK; credentials via Workload Identity in GKE (no key files).
Model ID comes from env var LLM_MODEL_ID — never hard-coded (ADR-005).
"""

from __future__ import annotations

import os
import time

import structlog

from app.provider.base import LLMProvider, LLMResponse

logger = structlog.get_logger(__name__)

_MODEL_ID = os.getenv("LLM_MODEL_ID", "gemini-2.5-flash")
_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
_PROJECT = os.getenv("GCP_PROJECT", "")


class VertexAIProvider(LLMProvider):
    """Calls Gemini via Vertex AI. Import google.generativeai ONLY inside this class."""

    def __init__(self) -> None:
        if not _PROJECT:
            raise ValueError("GCP_PROJECT env var is required for VertexAIProvider")
        # Lazy import so the mock provider works in CI without the SDK installed.
        import vertexai  # type: ignore[import-untyped]
        from vertexai.generative_models import GenerativeModel  # type: ignore[import-untyped]

        vertexai.init(project=_PROJECT, location=_LOCATION)
        self._model = GenerativeModel(_MODEL_ID)

    @property
    def model_id(self) -> str:
        return _MODEL_ID

    async def complete(
        self,
        system_prompt: str,
        data_block: str,
        *,
        temperature: float = 0.2,
        max_output_tokens: int = 1024,
    ) -> LLMResponse:
        from vertexai.generative_models import GenerationConfig  # type: ignore[import-untyped]

        prompt = f"{system_prompt}\n\n<data>\n{data_block}\n</data>"
        config = GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json",
        )

        t0 = time.monotonic()
        response = await self._model.generate_content_async(prompt, generation_config=config)
        latency = (time.monotonic() - t0) * 1000

        usage = response.usage_metadata
        return LLMResponse(
            content=response.text,
            model_id=_MODEL_ID,
            input_tokens=usage.prompt_token_count,
            output_tokens=usage.candidates_token_count,
            latency_ms=latency,
        )
