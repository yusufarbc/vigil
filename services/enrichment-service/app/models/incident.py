"""
Shared Pydantic models for enrichment-service.
Incident is the incoming message (from alert-gateway via Pub/Sub).
EnrichedIncident is the outgoing message (to masking-service via Pub/Sub).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Alert(BaseModel):
    id: str
    timestamp: datetime
    rule_id: str
    rule_name: str
    severity: str
    mitre_technique_ids: list[str] = Field(default_factory=list)
    mitre_technique_names: list[str] = Field(default_factory=list)
    host_name: str
    user_name: str
    source_ip: str | None = None
    process_name: str | None = None
    event_details: dict[str, str] = Field(default_factory=dict)


class Incident(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    alerts: list[Alert]
    alert_count: int
    affected_hosts: list[str]
    affected_users: list[str]
    source_ips: list[str]
    mitre_techniques: list[str]
    risk_score: int
    status: str
    correlation_key: str


class HostContext(BaseModel):
    name: str
    criticality: str = "unknown"
    owner: str | None = None
    os: str | None = None
    tags: list[str] = Field(default_factory=list)


class UserContext(BaseModel):
    name: str
    department: str | None = None
    privileged: bool = False


class IPContext(BaseModel):
    ip: str
    geo_country: str | None = None
    threat_intel_match: bool = False
    asn: str | None = None


class EnrichedIncident(BaseModel):
    """Output of enrichment-service; input to masking-service."""

    incident_id: str
    summary: str
    affected_hosts: list[HostContext]
    affected_users: list[UserContext]
    source_ips: list[IPContext]
    timeline: list[dict[str, Any]]
    mitre_techniques: list[str]
    risk_score: int
    alert_count: int
    raw_incident: Incident
