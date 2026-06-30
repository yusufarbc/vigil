"""
JSON schema that every LLM response MUST conform to.
The LLM is forced to return structured JSON (response_mime_type=application/json).
Non-conforming responses are rejected and re-tried or sent to the DLQ.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TriageDecision(BaseModel):
    """Output contract of llm-orchestrator. Published to sentinel.triage-decisions."""

    incident_id: str
    model_id: str
    severity_suggestion: str = Field(pattern="^(critical|high|medium|low)$")
    mitre_techniques_confirmed: list[str]
    false_positive_likelihood: float = Field(ge=0.0, le=1.0)
    summary: str
    recommended_actions: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    prompt_hash: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
