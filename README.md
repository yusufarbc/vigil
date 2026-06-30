# vigil — AI-Assisted SOC/NOC Platform

An open-source, AI-assisted Security & Network Operations platform built on the **free/Basic-licensed Elastic Stack**. Sentinel ingests telemetry, detects threats with Elastic SIEM detection rules (MITRE ATT&CK mapped), correlates alerts into incidents, and uses **Gemini 2.5 Flash via Vertex AI** as a triage assistant — never as an autonomous decision-maker.

> **Working language of the entire system, code, comments, logs, prompts, and UI: English.**

---

## Architecture

### Alert-to-Decision Pipeline

```mermaid
flowchart LR
    subgraph src["Log Sources"]
        W["Windows\nWinlogbeat · WEF"]
        FW["Firewall\nFortiGate · PaloAlto"]
        EDR["EDR\nKaspersky"]
        SYS["Syslog\nRFC 3164/5424"]
    end

    subgraph elastic["Elasticsearch — ECK on GKE"]
        IDX[("Indices\nhot tier 0–14 d")]
        SIEM["Kibana SIEM\nBasic detection rules\n40+ MITRE ATT&CK"]
    end

    subgraph pubsub["GCP Pub/Sub"]
        P1(["sentinel\n.alerts"])
        P2(["sentinel\n.incidents"])
        P3(["sentinel\n.masked-incidents"])
        P4(["sentinel\n.triage-decisions"])
    end

    subgraph services["Sentinel Services — GKE Autopilot"]
        DS["detection-service\nGo\npoll · normalize"]
        AG["alert-gateway\nGo\ndedup · correlate\nrisk-score"]
        EN["enrichment-service\nPython\nGeoIP · TI · asset"]
        MSK["masking-service\nPython\nPII → tokens\nreverse-map in ES"]
        LLM["llm-orchestrator\nPython\nONLY LLM caller"]
        CS["case-service\nGo\nunmask · human review"]
        BFF["bff\nGo\nanalyst API · UI"]
    end

    VA(["Vertex AI\nGemini 2.5 Flash"])

    SIEM -- "KQL · EQL · threshold" --> IDX
    W & FW & EDR & SYS -->|"Logstash / Beats / OTel"| IDX
    IDX -->|"poll alerts"| DS
    DS --> P1 --> AG
    AG --> P2 --> EN
    EN -->|"HTTP /mask"| MSK
    MSK --> P3 --> LLM
    LLM <-->|"JSON schema\ntriage"| VA
    LLM --> P4 --> CS --> BFF

    style VA  fill:#4285f4,color:#fff,stroke:#2a6dd9
    style LLM fill:#34a853,color:#fff,stroke:#1e7e34
    style MSK fill:#ea4335,color:#fff,stroke:#c0392b
    style IDX fill:#ff6d00,color:#fff,stroke:#e65100
```

### GCP Deployment Architecture

```mermaid
flowchart TB
    subgraph gke["GKE Autopilot"]
        subgraph ns["namespace: sentinel"]
            subgraph eck["ECK — Elasticsearch Cluster (3 nodes · PDB · anti-affinity)"]
                ES1[("ES node 1\n50 Gi SSD")]
                ES2[("ES node 2\n50 Gi SSD")]
                ES3[("ES node 3\n50 Gi SSD")]
                KIB["Kibana"]
            end
            subgraph svcs["Microservices (HPA)"]
                DS2["detection-service\n1–3 pods"]
                AG2["alert-gateway\n2–5 pods"]
                EN2["enrichment-service\n1–3 pods"]
                MSK2["masking-service\n2–4 pods"]
                LLM2["llm-orchestrator\n1–2 pods"]
                CS2["case-service\n1–3 pods"]
                BFF2["bff\n2–5 pods\nLoadBalancer :80"]
            end
        end
    end

    subgraph managed["GCP Managed Services"]
        PS["Cloud Pub/Sub\n5 topics · 4 subscriptions"]
        VA2["Vertex AI\nGemini 2.5 Flash\nus-central1"]
        AR["Artifact Registry\ncontainer images"]
        GCS["Cloud Storage\nES snapshots\nStandard → Archive"]
        WI["Workload Identity\nno API key files in pods"]
    end

    subgraph cicd["CI / CD — GitHub Actions"]
        direction LR
        CI1["lint → test\n→ SAST → SCA"]
        CI2["Docker build\n→ Trivy scan"]
        CI3["push to AR\nmain branch only"]
        CI1 --> CI2 --> CI3
    end

    svcs <-->|"publish / subscribe"| PS
    LLM2 <-->|"Workload Identity auth"| VA2
    ES1 & ES2 & ES3 -->|"ILM snapshot\nat 14 days"| GCS
    AR -->|"image pull"| svcs
    WI -. "authenticates" .-> svcs
    WI -. "authenticates" .-> eck
    CI3 -->|"SHA-tagged image"| AR

    style gke     fill:#e8f5e9,stroke:#388e3c
    style eck     fill:#fff8e1,stroke:#f9a825
    style svcs    fill:#e3f2fd,stroke:#1976d2
    style managed fill:#fce4ec,stroke:#c62828
    style cicd    fill:#f3e5f5,stroke:#7b1fa2
```

**Core principles (see [CLAUDE.md](CLAUDE.md)):**

- **Deterministic core, LLM as ranker.** Rule-based logic decides; LLM only enriches and suggests.
- **LLM triggered per incident** — never per alert or per log. Cuts LLM request count by 10–50×.
- **All LLM input is masked** (no PII), all output is validated JSON, all calls are audit-logged.
- **Only `masking-service`** holds plaintext PII reverse-maps (stored in Elasticsearch — multi-replica safe).
- **Only `llm-orchestrator`** calls the LLM API.

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
git clone https://github.com/yusufarbc/Vigil.git && cd Vigil

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

## CI / CD

Two-branch flow (ADR-011):

```text
feature branch
      │
      ▼ PR
   test ──► lint → test → SAST/SCA → Docker build → Trivy scan
      │
      ▼ PR (requires green pipeline on test)
   main ──► same gates → push images to Artifact Registry
```

GitHub secrets required for image push (`main` only):

| Secret | Value |
| --- | --- |
| `GCP_PROJECT` | GCP project ID |
| `WIF_PROVIDER` | Workload Identity Federation provider resource name |
| `WIF_SERVICE_ACCOUNT` | GSA email with `roles/artifactregistry.writer` |

---

## Infrastructure

```text
infrastructure/
├── k8s/
│   ├── namespace.yaml           # sentinel namespace (apply first)
│   ├── eck/                     # ECK: 3-node ES cluster, Kibana, ILM, GCS snapshot repo
│   └── services/                # K8s manifests for all 7 microservices + shared ConfigMap
├── config/
│   ├── detection-rules/         # 40+ MITRE ATT&CK-mapped SIEM rules (KQL + EQL)
│   ├── logstash/                # Pipelines: FortiGate, Kaspersky, PaloAlto, Windows WEF, Syslog
│   ├── elasticsearch/           # elasticsearch.yml
│   ├── kibana/                  # kibana.yml
│   └── elastic/                 # Fleet policy templates
├── client-configs/              # Windows GPO: Winlogbeat, Metricbeat, Heartbeat, Sysmon
└── scripts/                     # ELK bare-metal setup (Ubuntu Jammy), Sysmon installer
```

### Ingestion sources

| Source | Pipeline |
| --- | --- |
| Windows Event Logs (Winlogbeat / WEF) | `windows_wef.conf` |
| Syslog (RFC3164 / RFC5424) | `syslog.conf` |
| Palo Alto firewall | `paloalto.conf`, `paloalto_syslog.conf` |
| FortiGate firewall | `fortigate.conf` |
| Kaspersky EDR | `kaspersky.conf` |
| Libraesva email gateway | `libraesva.conf` |

### Detection rules

40+ MITRE ATT&CK-mapped rules in [`infrastructure/config/detection-rules/siem.rules.yml`](infrastructure/config/detection-rules/siem.rules.yml), covering:
Initial Access · Execution · Credential Access · Persistence · Lateral Movement · Defense Evasion · Firewall anomalies.

---

## Development

```bash
make test       # go test -race + pytest for all services
make lint       # golangci-lint + ruff for all services
make build      # docker compose build
```

```bash
# Individual Go service
cd services/detection-service && go test ./... -race

# Individual Python service
cd services/masking-service
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Production Deploy (GKE)

```bash
# Apply all K8s manifests in order
GCP_PROJECT=your-project IMAGE_TAG=abc1234 make apply-k8s

# Or manually step by step:
kubectl apply -f infrastructure/k8s/namespace.yaml
kubectl apply -f infrastructure/k8s/eck/
envsubst < infrastructure/k8s/services/configmap.yaml | kubectl apply -f -
# ... then each service manifest
```

**Credentials:** Workload Identity — no API key files in pods (ADR-006).  
**LLM:** Set `LLM_PROVIDER=vertex` and `GCP_PROJECT=<your-project>` (already set in the llm-orchestrator manifest).

---

## Architecture Decisions

Full log in [DECISIONS.md](DECISIONS.md). Key decisions:

| ADR | Decision |
| --- | --- |
| ADR-001 | LLM per incident, never per alert |
| ADR-004 | Mandatory PII masking before LLM |
| ADR-005 | Gemini 2.5 Flash (Vertex AI) · Claude Haiku 4.5 fallback |
| ADR-008 | Self-hosted Elasticsearch via ECK (not Elastic Cloud) |
| ADR-012 | Go (operational) + Python (AI/enrichment) |
| ADR-013 | GCP Pub/Sub (not Kafka) |
| ADR-014 | Elastic Basic-tier audit: ELSER / risk scoring / ML jobs blocked |
| ADR-015 | masking-service reverse-map stored in Elasticsearch (multi-replica safe) |
| ADR-016 | GKE Autopilot · `node.store.allow_mmap=false` for Autopilot compatibility |

---

## License

[MIT](LICENSE)
