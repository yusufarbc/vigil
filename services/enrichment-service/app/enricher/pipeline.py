"""Enrichment pipeline: runs all enrichers in order and produces an EnrichedIncident."""

from __future__ import annotations

import structlog

from app.enricher.base import Enricher
from app.models import EnrichedIncident, HostContext, Incident, IPContext, UserContext

logger = structlog.get_logger(__name__)


class EnrichmentPipeline:
    def __init__(self, enrichers: list[Enricher]) -> None:
        self._enrichers = enrichers

    async def run(self, incident: Incident) -> EnrichedIncident:
        partial = EnrichedIncident(
            incident_id=incident.id,
            summary=_build_summary(incident),
            affected_hosts=[HostContext(name=h) for h in incident.affected_hosts],
            affected_users=[UserContext(name=u) for u in incident.affected_users],
            source_ips=[IPContext(ip=ip) for ip in incident.source_ips],
            timeline=[
                {
                    "timestamp": a.timestamp.isoformat(),
                    "rule": a.rule_name,
                    "host": a.host_name,
                    "severity": a.severity,
                }
                for a in incident.alerts
            ],
            mitre_techniques=incident.mitre_techniques,
            risk_score=incident.risk_score,
            alert_count=incident.alert_count,
            raw_incident=incident,
        )

        for enricher in self._enrichers:
            try:
                partial = await enricher.enrich(incident, partial)
            except Exception:
                logger.exception("enricher failed", enricher=type(enricher).__name__)

        return partial


def _build_summary(incident: Incident) -> str:
    """Deterministic text summary passed to the LLM as context (not raw logs)."""
    techniques = ", ".join(incident.mitre_techniques) if incident.mitre_techniques else "unknown"
    hosts = ", ".join(incident.affected_hosts) or "unknown"
    return (
        f"{incident.alert_count} alert(s) in {len(incident.affected_hosts)} host(s) "
        f"({hosts}), risk score {incident.risk_score}/100, "
        f"MITRE techniques: {techniques}."
    )
