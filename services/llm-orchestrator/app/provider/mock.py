"""
Mock LLM provider for CI and local development.
NEVER hits the billed API. Returns deterministic, valid JSON that passes schema validation.
"""

from __future__ import annotations

import asyncio
import json
import time

from app.provider.base import LLMProvider, LLMResponse

MOCK_TRIAGE_RESPONSE = {
    "severity_suggestion": "high",
    "mitre_techniques_confirmed": ["T1059"],
    "false_positive_likelihood": 0.05,
    "summary": "Mock triage: suspicious process execution detected on affected host.",
    "recommended_actions": [
        "Isolate affected host",
        "Reset credentials of affected user",
        "Review process execution logs",
    ],
    "confidence": 0.85,
    "rationale": "Mock rationale for CI testing. Replace with real LLM response in production.",
}


class MockLLMProvider(LLMProvider):
    """Deterministic mock — safe for CI, tests, and local development."""

    @property
    def model_id(self) -> str:
        return "mock-llm-v1"

    async def complete(
        self,
        system_prompt: str,
        data_block: str,
        *,
        temperature: float = 0.2,
        max_output_tokens: int = 1024,
    ) -> LLMResponse:
        await asyncio.sleep(0.01)  # simulate minimal latency
        content = json.dumps(MOCK_TRIAGE_RESPONSE)
        return LLMResponse(
            content=content,
            model_id=self.model_id,
            input_tokens=len(system_prompt.split()) + len(data_block.split()),
            output_tokens=len(content.split()),
            latency_ms=10.0,
        )
