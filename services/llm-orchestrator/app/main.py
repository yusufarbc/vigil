"""llm-orchestrator entry point.

The ONLY service that calls the LLM API.
Subscribes to sentinel.masked-incidents, calls triage(), publishes TriageDecision.
Provider is selected by LLM_PROVIDER env var: "mock" (default) | "vertex".
"""

from __future__ import annotations

import asyncio
import os
import signal

import structlog

from app.orchestrator import BudgetTracker, LLMOrchestrator
from app.provider import MockLLMProvider, VertexAIProvider

logger = structlog.get_logger(__name__)

_PROVIDER_NAME = os.getenv("LLM_PROVIDER", "mock")
_MAX_TOKENS_PER_WINDOW = int(os.getenv("LLM_MAX_TOKENS_PER_WINDOW", "500000"))


def _build_provider():
    if _PROVIDER_NAME == "vertex":
        return VertexAIProvider()
    logger.info("LLM_PROVIDER=mock — using MockLLMProvider (no billed API calls)")
    return MockLLMProvider()


async def main() -> None:
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(20))

    provider = _build_provider()
    budget = BudgetTracker(max_tokens_per_window=_MAX_TOKENS_PER_WINDOW)
    _orchestrator = LLMOrchestrator(provider=provider, budget_tracker=budget)

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    logger.info(
        "llm-orchestrator starting",
        provider=_PROVIDER_NAME,
        model=provider.model_id,
        budget=_MAX_TOKENS_PER_WINDOW,
    )

    # Phase 1: stub loop — Phase 2 adds Pub/Sub subscriber.
    await stop.wait()
    logger.info("llm-orchestrator stopped")


if __name__ == "__main__":
    asyncio.run(main())
