"""masking-service — the ONLY service that holds plaintext PII reverse-maps.

Exposes a minimal HTTP API used by enrichment-service (mask) and case-service (unmask).
In production, reverse-maps are persisted in Elasticsearch (ADR-015) so multiple
replicas can share state without coordination.
"""

from __future__ import annotations

import os

import structlog
import uvicorn
from elasticsearch import AsyncElasticsearch
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.masker import ElasticsearchMasker
from app.models import MaskRequest, MaskResponse, UnmaskRequest, UnmaskResponse

logger = structlog.get_logger(__name__)

_ELASTIC_URL = os.getenv("ELASTIC_URL", "http://localhost:9200")
_ELASTIC_USER = os.getenv("ELASTIC_USER", "elastic")
_ELASTIC_PASSWORD = os.getenv("ELASTIC_PASSWORD", "")
_ELASTIC_CA_CERTS = os.getenv("ELASTIC_CA_CERTS", "")

app = FastAPI(title="masking-service", version="0.1.0")


def _build_es() -> AsyncElasticsearch:
    kwargs: dict = {
        "hosts": [_ELASTIC_URL],
        "basic_auth": (_ELASTIC_USER, _ELASTIC_PASSWORD),
    }
    if _ELASTIC_CA_CERTS:
        kwargs["ca_certs"] = _ELASTIC_CA_CERTS
    return AsyncElasticsearch(**kwargs)


_es = _build_es()
_masker = ElasticsearchMasker(_es)


@app.on_event("startup")
async def startup() -> None:
    await _masker.ensure_index()
    logger.info("masking-service started", elastic_url=_ELASTIC_URL)


@app.on_event("shutdown")
async def shutdown() -> None:
    await _es.close()


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/mask", response_model=MaskResponse)
async def mask(req: MaskRequest) -> MaskResponse:
    token = await _masker.mask(req.incident_id, req.kind, req.plaintext)
    return MaskResponse(token=token)


@app.post("/unmask", response_model=UnmaskResponse)
async def unmask(req: UnmaskRequest) -> UnmaskResponse:
    plaintext = await _masker.unmask(req.incident_id, req.token)
    return UnmaskResponse(plaintext=plaintext)


@app.delete("/map/{incident_id}", status_code=204)
async def delete_map(incident_id: str) -> JSONResponse:
    await _masker.delete_map(incident_id)
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
