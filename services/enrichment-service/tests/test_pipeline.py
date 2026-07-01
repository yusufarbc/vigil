"""Unit tests for EnrichmentPipeline — no external dependencies."""

import asyncio
from datetime import UTC, datetime

from app.enricher import EnrichmentPipeline
from app.models import Alert, Incident


def _make_incident() -> Incident:
    alert = Alert(
        id="a1",
        timestamp=datetime.now(UTC),
        rule_id="WIN-001",
        rule_name="Office macro spawned cmd",
        severity="high",
        mitre_technique_ids=["T1059"],
        mitre_technique_names=["Command and Scripting Interpreter"],
        host_name="PC-01",
        user_name="john.doe",
    )
    return Incident(
        id="inc-001",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        alerts=[alert],
        alert_count=1,
        affected_hosts=["PC-01"],
        affected_users=["john.doe"],
        source_ips=[],
        mitre_techniques=["T1059"],
        risk_score=25,
        status="pending_triage",
        correlation_key="PC-01|john.doe|T1059",
    )


def test_pipeline_no_enrichers_produces_base_output():
    pipeline = EnrichmentPipeline(enrichers=[])
    incident = _make_incident()
    result = asyncio.get_event_loop().run_until_complete(pipeline.run(incident))

    assert result.incident_id == "inc-001"
    assert result.risk_score == 25
    assert "PC-01" in result.summary
    assert len(result.affected_hosts) == 1
    assert result.affected_hosts[0].name == "PC-01"


def test_summary_contains_mitre_technique():
    pipeline = EnrichmentPipeline(enrichers=[])
    incident = _make_incident()
    result = asyncio.get_event_loop().run_until_complete(pipeline.run(incident))
    assert "T1059" in result.summary
