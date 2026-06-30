"""
Audit logger for every LLM call. Mandatory per CLAUDE.md §4 and §6.
Logs: prompt_hash, full masked prompt, full response, model id+version,
      token counts, latency_ms, resulting_decision.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import structlog

logger = structlog.get_logger("llm.audit")


def log_call(
    *,
    incident_id: str,
    model_id: str,
    system_prompt: str,
    data_block: str,
    response_content: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float,
    resulting_decision: dict,
) -> None:
    prompt_full = f"{system_prompt}\n\n<data>\n{data_block}\n</data>"
    prompt_hash = hashlib.sha256(prompt_full.encode()).hexdigest()

    logger.info(
        "llm_call",
        incident_id=incident_id,
        model_id=model_id,
        prompt_hash=prompt_hash,
        prompt=prompt_full,          # masked — no PII reaches here (ADR-004)
        response=response_content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=round(latency_ms, 1),
        resulting_decision=resulting_decision,
        ts=datetime.now(timezone.utc).isoformat(),
    )
