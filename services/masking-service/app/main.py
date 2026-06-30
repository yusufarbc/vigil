"""masking-service — the ONLY service that holds plaintext PII reverse-maps.

Exposes a minimal HTTP API used by enrichment-service (mask) and case-service (unmask).
Pub/Sub: receives EnrichedIncident from enrichment-service, masks PII fields,
publishes MaskedIncident to sentinel.masked-incidents.
"""

from __future__ import annotations

import os

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.masker import Masker
from app.models import MaskRequest, MaskResponse, UnmaskRequest, UnmaskResponse

logger = structlog.get_logger(__name__)

app = FastAPI(title="masking-service", version="0.1.0")
_masker = Masker()


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/mask", response_model=MaskResponse)
async def mask(req: MaskRequest) -> MaskResponse:
    token = _masker.mask(req.incident_id, req.kind, req.plaintext)
    return MaskResponse(token=token)


@app.post("/unmask", response_model=UnmaskResponse)
async def unmask(req: UnmaskRequest) -> UnmaskResponse:
    plaintext = _masker.unmask(req.incident_id, req.token)
    return UnmaskResponse(plaintext=plaintext)


@app.delete("/map/{incident_id}", status_code=204)
async def delete_map(incident_id: str) -> JSONResponse:
    _masker.delete_map(incident_id)
    logger.info("reverse-map deleted", incident_id=incident_id)
    return JSONResponse(content=None, status_code=204)


if __name__ == "__main__":
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(20))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8001")),
        log_config=None,
    )
