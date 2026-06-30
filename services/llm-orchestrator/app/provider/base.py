"""
LLM provider interface. llm-orchestrator is the ONLY service that calls the LLM.
All concrete implementations must satisfy this interface — never import a vendor SDK
directly in business logic; import the interface here instead.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    model_id: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


class LLMProvider(ABC):
    """Swappable LLM backend. Current default: Vertex AI (Gemini 2.5 Flash)."""

    @property
    @abstractmethod
    def model_id(self) -> str: ...

    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        data_block: str,
        *,
        temperature: float = 0.2,
        max_output_tokens: int = 1024,
    ) -> LLMResponse: ...
