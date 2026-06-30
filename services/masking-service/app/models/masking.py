"""HTTP API contract for masking-service.

Only masking-service exposes this API. case-service calls /unmask.
enrichment-service calls /mask (or posts a full EnrichedIncident to /mask-incident).
"""

from __future__ import annotations

from pydantic import BaseModel


class MaskRequest(BaseModel):
    incident_id: str
    kind: str  # "user" | "host" | "ip" | "email"
    plaintext: str


class MaskResponse(BaseModel):
    token: str


class UnmaskRequest(BaseModel):
    incident_id: str
    token: str


class UnmaskResponse(BaseModel):
    plaintext: str | None
