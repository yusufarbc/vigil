# Sentinel — AI-Assisted SOC/NOC Platform

An open-source, AI-assisted Security & Network Operations platform built on the **free/Basic-licensed Elastic Stack**. Sentinel ingests telemetry, detects threats with Elastic SIEM detection rules (MITRE ATT&CK mapped), correlates alerts into incidents, and uses **Gemini 2.5 Flash via Vertex AI** as a triage assistant — never as an autonomous decision-maker.

> **Working language of the entire system, code, comments, logs, prompts, and UI: English.**

---

## Architecture

```
Logstash / Beats / OTel
        │
        ▼
   Elasticsearch ◄──── Kibana SIEM detection rules (Basic tier)
        │                        │
        │              .alerts-security.alerts-*
        │                        │
        ▼                        ▼
detection-service  ──[sentinel.alerts]──► alert-gateway
                                              │
                                     [sentinel.incidents]
                                              │
                                    enrichment-service
                                    (GeoIP · TI · asset)
                                              │
                                    masking-service  ◄── only PII reverse-map holder
                                              │
                                  [sentinel.masked-incidents]
                                              │
                                    llm-orchestrator  ◄── ONLY LLM caller
                                    (Vertex AI / mock)
                                              │
                                   [sentinel.triage-decisions]
                                              │
                                       case-service
                                   (unmask · human review)
                                              │
                                          bff / UI
```

**Core principles (see [CLAUDE.md](CLAUDE.md)):**

- Deterministic core, LLM as ranker. Rule-based logic decides; LLM only suggests.
- LLM triggered **per incident**, never per alert or per log.
- All LLM input is masked (no PII), all output is validated JSON, all calls are audit-logged.
- Only `masking-service` holds plaintext PII reverse-maps.
- Only `llm-orchestrator` calls the LLM API.

---

## Services

| Service | Language | Responsibility |
| --- | --- | --- |
| `detection-service` | Go | Reads ES alerts, normalizes, publishes to Pub/Sub |
| `alert-gateway` | Go | Dedup, correlation, risk scoring; forms incidents |
| `enrichment-service` | Python | GeoIP, threat-intel, asset criticality enrichment |
| `masking-service` | Python | PII pseudonymization + reverse-map HTTP API |
| `llm-orchestrator` | Python | LLM triage with provider interface (Vertex AI / mock) |
| `case-service` | Go | Unmasks, manages cases, human-review queue |
| `bff` | Go | Thin HTTP API for analyst triage UI |

---

## Quick Start (local dev)

**Prerequisites:** Docker, Docker Compose, `make`, `curl`

```bash
# 1. Clone and enter
git clone https://github.com/<your-org>/sentinel.git && cd sentinel

# 2. Copy env file (defaults work for local dev)
cp .env.example .env

# 3. Start everything
make up

# 4. Bootstrap Pub/Sub topics (run once after first start)
make pubsub-init

# Kibana:  http://localhost:5601
# BFF:     http://localhost:8080/healthz
```

> **LLM is mocked by default** (`LLM_PROVIDER=mock`). No Vertex AI credentials needed for local dev. The mock returns valid, schema-conformant triage decisions.

---

## Infrastructure

```
infrastructure/
├── k8s/eck/              # ECK 3-node Elasticsearch cluster + Kibana + ILM + GCS snapshots
├── k8s/services/         # Kubernetes manifests for Sentinel microservices
├── config/
│   ├── detection-rules/  # 40+ MITRE ATT&CK-mapped SIEM rules (KQL + EQL)
│   ├── logstash/         # Pipelines: FortiGate, Kaspersky, PaloAlto, Windows WEF, Syslog
│   ├── elasticsearch/    # elasticsearch.yml
│   ├── kibana/           # kibana.yml
│   └── elastic/          # Fleet policy templates
├── client-configs/       # Windows GPO: Winlogbeat, Metricbeat, Heartbeat, Sysmon
└── scripts/              # ELK bare-metal setup (Ubuntu Jammy), Sysmon installer
```

### Ingestion sources (Logstash pipelines)

| Source | Pipeline |
| --- | --- |
| Windows Event Logs (Winlogbeat / WEF) | `windows_wef.conf` |
| Syslog (RFC3164 / RFC5424) | `syslog.conf` |
| Palo Alto firewall | `paloalto.conf`, `paloalto_syslog.conf` |
| FortiGate firewall | `fortigate.conf` |
| Kaspersky EDR | `kaspersky.conf` |
| Libraesva email gateway | `libraesva.conf` |

### Detection rules

40+ MITRE ATT&CK-mapped detection rules in [`infrastructure/config/detection-rules/siem.rules.yml`](infrastructure/config/detection-rules/siem.rules.yml), covering:

- Initial Access & Execution (Office macro abuse, browser exploitation, WScript/PowerShell chains)
- Credential Access (LSASS dump, RDP brute force)
- Persistence (Registry Run keys, Scheduled Tasks, Windows Services)
- Lateral Movement (WMI remote execution, PsExec, SMB shares)
- Defense Evasion (Defender disabled, Windows event logs cleared)
- Firewall anomalies (bogon IPs, port scans, geo-based anomalies)

---

## Development

```bash
# All services
make test       # go test + pytest for all services
make lint       # golangci-lint + ruff for all services
make build      # docker compose build

# Individual Go service
cd services/detection-service
go mod tidy
go test ./... -race

# Individual Python service
cd services/masking-service
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .
pytest tests/ -v
```

---

## Production (GKE + ECK)

See [`infrastructure/k8s/eck/`](infrastructure/k8s/eck/) for:

- 3-node Elasticsearch cluster with PodDisruptionBudget and pod anti-affinity (ADR-009)
- ILM policy: 14-day hot tier → GCS snapshot → delete from hot (ADR-010)
- GCS snapshot repository registration

**Credentials:** Workload Identity — no API key files in pods (ADR-006).
**LLM provider:** Set `LLM_PROVIDER=vertex` and `GCP_PROJECT=<your-project>` in the deployment.

---

## Decisions

Architecture decision records are in [DECISIONS.md](DECISIONS.md). Key decisions:

| ADR | Decision |
| --- | --- |
| ADR-001 | LLM per incident, never per alert |
| ADR-004 | Mandatory PII masking before LLM |
| ADR-005 | Gemini 2.5 Flash (Vertex AI) · Claude Haiku 4.5 fallback |
| ADR-008 | Self-hosted Elasticsearch via ECK (not Elastic Cloud) |
| ADR-012 | Go (operational) + Python (AI/enrichment) |
| ADR-013 | GCP Pub/Sub (not Kafka) |
| ADR-014 | Elastic Basic-tier audit: ELSER / risk scoring / ML jobs blocked |

---

## License

[MIT](LICENSE)
