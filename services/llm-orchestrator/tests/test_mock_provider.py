"""Unit tests for MockLLMProvider — verifies the mock is schema-conformant."""

import asyncio
import json

import pytest

from app.provider.mock import MockLLMProvider
from app.triage_schema import TriageDecision


def test_mock_returns_valid_json():
    provider = MockLLMProvider()
    response = asyncio.get_event_loop().run_until_complete(
        provider.complete(system_prompt="sys", data_block="data")
    )
    parsed = json.loads(response.content)
    assert "severity_suggestion" in parsed
    assert "confidence" in parsed


def test_mock_response_passes_schema_validation():
    provider = MockLLMProvider()
    response = asyncio.get_event_loop().run_until_complete(
        provider.complete(system_prompt="sys", data_block="data")
    )
    raw = json.loads(response.content)
    # Should not raise
    decision = TriageDecision(
        incident_id="test-inc",
        model_id=provider.model_id,
        prompt_hash="abc123",
        input_tokens=10,
        output_tokens=5,
        latency_ms=10.0,
        **raw,
    )
    assert decision.severity_suggestion in ("critical", "high", "medium", "low")
    assert 0.0 <= decision.confidence <= 1.0
    assert 0.0 <= decision.false_positive_likelihood <= 1.0


def test_mock_model_id():
    assert MockLLMProvider().model_id == "mock-llm-v1"
