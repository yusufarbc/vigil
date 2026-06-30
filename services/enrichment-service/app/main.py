"""enrichment-service entry point.

Subscribes to sentinel.incidents (Pub/Sub), runs the enrichment pipeline,
and publishes EnrichedIncident to the masking-service via HTTP call.
Pub/Sub adapter and masking-service client are injected at startup from env vars.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal

import structlog

from app.enricher import EnrichmentPipeline
from app.models import Incident

logger = structlog.get_logger(__name__)

PUBSUB_PROJECT = os.getenv("PUBSUB_PROJECT", "sentinel-local")
INCIDENTS_SUBSCRIPTION = os.getenv("INCIDENTS_SUBSCRIPTION", "sentinel.incidents.enrichment-sub")
MASKING_SERVICE_URL = os.getenv("MASKING_SERVICE_URL", "http://masking-service:8001")


async def handle_message(data: bytes, pipeline: EnrichmentPipeline) -> None:
    try:
        incident = Incident.model_validate_json(data)
    except Exception:
        logger.exception("invalid incident message, skipping")
        return

    log = logger.bind(incident_id=incident.id)
    log.info("enriching incident")

    enriched = await pipeline.run(incident)

    # Phase 2: push enriched incident to masking-service via HTTP POST.
    log.info("enrichment complete", summary=enriched.summary)


async def main() -> None:
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(20))

    pipeline = EnrichmentPipeline(enrichers=[])  # Phase 2 adds GeoIP, TI, asset enrichers

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    logger.info("enrichment-service starting", project=PUBSUB_PROJECT)

    # Phase 1: stub loop — in Phase 2 this becomes a real Pub/Sub subscriber.
    await stop.wait()
    logger.info("enrichment-service stopped")


if __name__ == "__main__":
    asyncio.run(main())
