# DECISIONS.md

Architecture Decision Record (ADR) log for the Sentinel AI-assisted SOC/NOC platform. Each entry records the decision, the alternatives considered, the rationale, open risks, and the date. This is the companion to `CLAUDE.md`; `CLAUDE.md` states the rules, this file explains *why*.

Format per entry: **Decision · Status · Date · Context · Alternatives · Rationale · Risks / follow-ups.**

---

## ADR-001 — LLM is triggered per INCIDENT, never per alert or per log

**Status:** Accepted · **Date:** 2026-06-30

**Context:** The original idea was to send every alert (or every log) to the LLM at "first level" 24/7. At Fortune-500-scale log volumes this is economically and operationally unworkable.

**Alternatives considered:**
- Per-log LLM triage — rejected: astronomical cost, moves alert fatigue onto the LLM layer.
- Per-alert LLM triage — rejected: still 20–50x the request volume of incident-level, and the LLM sees fragments instead of the whole picture, producing lower-quality triage.
- Per-incident LLM triage — **chosen.**

**Rationale:** Aggregating related alerts into one incident before any LLM call cuts request count by 10–50x, gives the LLM full context (timeline + affected assets + triggered MITRE techniques) for better triage, and makes cost predictable. This single decision is the dominant cost lever — model choice is secondary.

**Risks / follow-ups:** Correlation/aggregation logic in `alert-gateway` must be solid; bad correlation either floods the LLM or merges unrelated events. Needs tuning and measurement.

---

## ADR-002 — Deterministic core, LLM as ranker; human-in-the-loop for all actions

**Status:** Accepted · **Date:** 2026-06-30

**Context:** SOC decisions must be auditable (KVKK, ISO 27001, SOC2). LLM output is non-deterministic and the LLM input is attacker-influenceable (a log line can contain injected instructions).

**Alternatives considered:**
- LLM auto-executes response actions (isolate host, block IP) — rejected: unsafe, non-auditable, prompt-injection exposure.
- LLM as advisory layer only, deterministic core decides, human approves actions — **chosen.**

**Rationale:** Rule-based logic makes decisions; the LLM enriches, summarizes, and *suggests* with a confidence and rationale. Every response action requires human approval in the phases covered here. Mirrors the proven "deterministic core, AI as option-ranker" pattern.

**Risks / follow-ups:** Must enforce structured JSON output with schema validation; must log prompt + response + model + version + tokens for every call.

---

## ADR-003 — Token & privacy minimization is achieved by context curation, NOT by RAG

**Status:** Accepted · **Date:** 2026-06-30

**Context:** The initial assumption was that RAG would reduce tokens sent to the LLM and improve privacy. RAG *adds* context to the prompt — it increases tokens. The real goals (fewer tokens, less sensitive data to the LLM) are met by other means.

**Alternatives considered:**
- Use RAG as the primary token/privacy reducer — rejected: RAG grows prompts; it is the wrong tool for reduction.
- Context curation (pre-aggregation, field selection, deterministic enrichment) + masking, with RAG reserved for org-specific knowledge only — **chosen.**

**Rationale:**
- **Request count** is reduced by tuning + correlation + incident aggregation (ADR-001).
- **Tokens per request** are reduced by sending curated, aggregated features (e.g. "500 failed logins from 3 IPs in 10 min on host X") instead of raw log lines, and by selecting only the handful of fields needed for triage.
- **Deterministic enrichment** (GeoIP, threat-intel match, asset criticality) is resolved in code and passed as short strings, not handed to the LLM as raw data to reason over.
- **RAG** is used only for organization-specific knowledge the model does not have (internal playbooks, past incident dispositions, asset context) — never for general MITRE/CVE knowledge the model already holds.

**Risks / follow-ups:** Curation logic must not strip detail needed for correct triage; balance is empirical and needs tuning.

---

## ADR-004 — Mandatory PII masking / pseudonymization before the LLM

**Status:** Accepted · **Date:** 2026-06-30

**Context:** Privacy concern about company logs reaching a US-origin LLM API, plus KVKK cross-border transfer exposure, plus prompt-injection surface reduction.

**Alternatives considered:**
- Send raw identifiers (usernames, IPs, hostnames, emails) to the LLM — rejected: privacy, compliance, and injection risks.
- Reversible pseudonymization before the LLM, un-mask after — **chosen.**

**Rationale:** Identifiers are mapped to stable tokens (`user_a1`, `host_x3`, `ip_7`) before anything reaches `llm-orchestrator`. A reverse-map is held per incident by a single component (`masking-service`). The LLM reasons over masked data; `case-service` un-masks the decision. This is a compliance control, not an optimization. Note: running the LLM via Vertex AI in-region (ADR-006) further reduces transfer exposure; masking is defense-in-depth on top of that.

**Risks / follow-ups:** Only `masking-service` may hold plaintext reverse-maps. Reverse-map lifecycle (TTL, deletion) must be defined. Legal review of cross-border transfer still recommended even with masking + in-region inference.

---

## ADR-005 — LLM model: Gemini 2.5 Flash, behind a swappable provider interface

**Status:** Accepted · **Date:** 2026-06-30

**Context:** Requirement: US-origin commercial model, billed API, system runs entirely in English. Candidates compared: Claude Haiku 4.5 vs Gemini 2.5 Flash vs Gemini 3.5 Flash vs Gemini 3.1 Flash-Lite.

**Pricing compared (USD per million tokens, standard; verify before budgeting — prices change fast):**
| Model | Input | Output |
|---|---|---|
| Claude Haiku 4.5 | $1.00 | $5.00 |
| Gemini 2.5 Flash | $0.30 | $2.50 |
| Gemini 3.5 Flash | $1.50 | $9.00 |
| Gemini 3.1 Flash-Lite | $0.25 | $1.50 |

**Estimated monthly cost** (assuming correct incident-level architecture: ~500 incidents/day, ~3,000 input + ~800 output tokens each): Gemini 2.5 Flash ≈ $44/mo; Haiku 4.5 ≈ $105/mo; Gemini 3.5 Flash ≈ $176/mo. All negligible at this scale — **architecture, not model, determines cost.**

**Alternatives considered:**
- Claude Haiku 4.5 — strong instruction-following, structured-output discipline, injection resistance; kept as the documented fallback for A/B testing and for escalated incidents.
- Gemini 3.5 Flash — newer default but more expensive than Haiku; not chosen for cost reasons.
- Gemini 2.5 Flash — **chosen** as default: US-origin, cheapest viable, 1M context, and consolidates onto GCP (ADR-006).

**Rationale:** Triage (summarization, MITRE-mapping interpretation, structured JSON, prioritization) is squarely in the Flash/Haiku capability class. Gemini 2.5 Flash chosen for cost + GCP consolidation. The provider/model MUST sit behind an interface so Haiku (or any model) can be swapped via one adapter without touching business logic — preserves the "no vendor lock-in / digital sovereignty" principle.

**Risks / follow-ups:**
- Run a one-week A/B of Gemini 2.5 Flash vs Haiku on real incidents; measure MITRE-mapping accuracy, false-positive capture, and JSON conformance. Let quality decide, since cost is negligible either way.
- Implement tiered routing: default to Flash; escalate complex/high-stakes incidents to a stronger model.
- Model IDs change/deprecate fast — keep the model ID in config, never hard-coded.

---

## ADR-006 — Run the LLM via GCP Vertex AI (NOT Google AI Studio)

**Status:** Accepted · **Date:** 2026-06-30

**Context:** The whole platform runs on GCP/GKE. The LLM can be called via Vertex AI (enterprise surface) or Google AI Studio / Gemini Developer API (dev/prototype surface). These are different products with different data-handling terms.

**Alternatives considered:**
- Google AI Studio / Gemini Developer API — rejected for production: free tier may use content to improve Google's products; weaker enterprise governance.
- Vertex AI — **chosen.**

**Rationale:** Vertex AI keeps inference inside the GCP org boundary, allows region pinning, integrates with Workload Identity (no API-key files for GKE services), VPC Service Controls, and unified billing/observability with Pub/Sub, GKE, and Elasticsearch. Directly supports the privacy posture in ADR-004. `llm-orchestrator` implements the Vertex AI SDK behind the swappable interface from ADR-005.

**Risks / follow-ups:** Confirm region and data-processing terms contractually. Must use paid tier — never free tier — because the system processes log data.

---

## ADR-007 — GKE + Kubernetes for the platform; stateless services autoscale

**Status:** Accepted · **Date:** 2026-06-30

**Context:** Containerized microservice architecture with autoscaling, deployed on a major cloud. GKE chosen for native Kubernetes.

**Alternatives considered:** AWS / Azure — viable, but GCP chosen for native K8s + consolidation with Vertex AI (ADR-006) and GCS archival (ADR-009).

**Rationale:** The custom microservices (alert-gateway, enrichment, masking, llm-orchestrator, case-service, bff, response) are **stateless** — pods are cattle, not pets; HPA scales them trivially because they hold no persistent data. Kubernetes is ideal for this. Elasticsearch is the one stateful exception, handled separately (ADR-008).

**Risks / follow-ups:** Keep state out of the stateless services; Elasticsearch is the system of record for telemetry.

---

## ADR-008 — Elasticsearch self-hosted via ECK on GKE (open source, AGPLv3/ELv2) — NOT Elastic Cloud

**Status:** Accepted · **Date:** 2026-06-30

**Context:** Goal is a fully free, open-source, self-hosted stack aligned with the "digital sovereignty" philosophy. Two separate concepts were clarified: (a) software *license* — Elasticsearch/Kibana are open source again since Sept 2024 (AGPLv3 added alongside SSPL and ELv2); self-hosted use inside our own application is free and permitted under ELv2/AGPLv3. (b) deployment *model* — Elastic Cloud is a paid *managed operations service*, not a license cost.

**Alternatives considered:**
- Elastic Cloud (managed) — rejected: it's a paid subscription for operations and conflicts with the self-hosted/sovereignty goal, even though the underlying software is free.
- GCP-native search alternative (e.g. OpenSearch fork) — rejected: the architecture is built around Elastic's detection/SIEM/vector features; switching is a large change.
- ECK on GKE, self-hosted — **chosen.**

**Rationale:** Self-hosting under AGPLv3/ELv2 is free and sovereignty-aligned. ELv2 only forbids reselling Elasticsearch as a managed service — which we don't do. The org-specific RAG store (ADR-003) can live inside the same self-hosted Elasticsearch via `dense_vector`/ELSER — no separate vector DB needed (verify ELSER's license tier; fall back to `dense_vector` + self-hosted embeddings if ELSER is not in Basic).

**Trade-off accepted:** The stateful SRE burden (storage management, snapshots, rolling upgrades, shard rebalancing, JVM/heap tuning, cluster health) is **ours**, by deliberate choice. This is not a mistake to avoid — it is the cost of sovereignty. With a two-person team, manage it by starting small and automating early (ADR-009).

**Risks / follow-ups:** Verify which Elastic features (detection rules, ML jobs, entity risk scoring, ELSER, searchable snapshots) are available in the free/Basic tier before depending on them; record any paid dependency here.

---

## ADR-009 — Stateful operations baseline: 3-node MVP cluster, ILM, GCS snapshots

**Status:** Accepted · **Date:** 2026-06-30

**Context:** Elasticsearch pods run 24/7 in containers, but "staying up" is an *active* state achieved by correct configuration, not a passive one. A disk-full or OOM cluster is "up but not working."

**Decisions:**
- **Cluster size (MVP):** 3 nodes — gives master quorum and avoids split-brain; no need for a large cluster at MVP.
- **StatefulSet + PersistentVolumeClaim:** managed by ECK so each pod re-binds to its own disk on restart.
- **PodDisruptionBudget + anti-affinity:** prevent all nodes landing on one physical machine / all dying together.
- **Resource requests/limits:** size RAM so heap (≈half of pod RAM) is sufficient; otherwise pods OOM-restart.
- **ILM from day one:** hot tier holds **14 days** of searchable data; after 14 days, snapshot then delete from hot tier to free disk. SOC log volume fills disk fast — without ILM the cluster jams within days (disk >85% flips indices read-only).

**Rationale:** These are the infrastructure that *makes* "always up" true. ECK automates the heavy lifting (StatefulSet orchestration, rolling upgrades, cluster formation); our job is ILM, snapshots, resource planning, and monitoring.

**Risks / follow-ups:** Test snapshot *restore*, not just snapshot. Monitor disk utilization actively.

---

## ADR-010 — Archive tier: GCS object storage (NOT Google Drive)

**Status:** Accepted · **Date:** 2026-06-30

**Context:** After 14 days of hot data, older data is archived elsewhere. Google Drive was suggested as the archive target.

**Alternatives considered:**
- Google Drive — rejected: Drive is a file-sharing service, not object storage. Elasticsearch snapshot repositories require S3-compatible / GCS blob storage. There is no "snapshot to Drive" path; Drive also has quota/file-count limits and no storage-class tiering.
- GCS (Google Cloud Storage) — **chosen.**

**Rationale:** Already on GCP. Elasticsearch has an official GCS snapshot repository plugin. GCS storage classes (Standard → Nearline → Coldline → Archive) auto-reduce cost as data ages via a lifecycle policy — ideal for rarely-accessed SOC log archives.

**Two archive concepts distinguished:**
1. **Snapshot archive (disaster recovery):** full index/cluster backups to GCS. Always required.
2. **Searchable archive (still queryable old data):** Elasticsearch "searchable snapshots" — **verify license tier**; may be a paid feature, may not be in Basic/open-source. Do not depend on it until confirmed.

**Chosen default flow:** ILM snapshots the index to GCS at 14 days, deletes it from hot tier; raw snapshot sits in GCS (Archive class) for infrequent restore (audit/forensics). If frequent fast search over old data is later required, revisit searchable snapshots (license + cost question).

**ILM flow:**
```
New log → Hot tier (Elasticsearch, GKE disk)   [0–14 days]  fast, active triage
   ↓ at 14 days
Snapshot → GCS bucket                          [archive]    object storage, not Drive
   ↓
Delete index from hot tier                                  free the disk
   ↓ GCS lifecycle policy
GCS: Standard → Nearline → Coldline → Archive  [as it ages] cost drops
```

**Risks / follow-ups:** Legal/regulatory retention period (KVKK, sector rules) is a SEPARATE decision from the 14-day operational hot window — security logs may carry a longer mandated retention. Set GCS retention to the regulatory requirement; do not conflate it with the hot window.

---

## ADR-011 — Engineering process: GitHub two-branch flow, DevSecOps CI/CD, GKE deploy

**Status:** Accepted · **Date:** 2026-06-30

**Context:** SOLID design, CI/CD pipeline, DevSecOps cycle required.

**Decisions:**
- **Branches:** `test` (integration) and `main` (release); PRs into `main` require a green pipeline.
- **CI/CD (GitHub Actions) gates:** lint → unit tests → SAST → dependency/SCA scan → container build → image vulnerability scan → IaC scan → push image to registry → deploy. Fail on high-severity findings.
- **Testing:** unit tests per service; contract tests at boundaries; one end-to-end integration test driving a synthetic incident with a **mocked LLM** — never hit the billed API in CI.
- **Cost guardrail:** the queue (Pub/Sub) is the cost gate; `llm-orchestrator` has a per-window budget circuit-breaker — when exceeded, queue incidents for human triage instead of calling the API.

**Rationale:** Aligns with the stated SOLID + DevSecOps goals and protects against runaway API spend and untested releases.

**Risks / follow-ups:** Keep secrets out of code (use Workload Identity, ADR-006). Monitor LLM cost, request rate, and triage latency as first-class metrics.

---

## ADR-012 — Backend language split: Go for operational services, Python for AI/enrichment services

**Status:** Accepted · **Date:** 2026-06-30

**Context:** CLAUDE.md §3 requires justifying the language split. Services divide into two groups: (a) high-throughput, long-running daemons where binary size, startup latency, and resource footprint matter (`detection-service`, `alert-gateway`, `case-service`, `response-service`, `bff`); (b) AI/ML pipeline services where the Python ecosystem (Pydantic, LangChain-style async, Vertex AI SDK, spaCy for NER/masking) gives a productivity advantage (`enrichment-service`, `masking-service`, `llm-orchestrator`).

**Alternatives considered:**

- All Go — would require reimplementing ecosystem tooling for AI/NLP; available Vertex AI SDK for Go is less mature than Python.
- All Python — GIL limits true parallelism for the stateless fan-out services; larger container images; slower cold-start for HPA scale-from-zero.
- Go for operational + Python for AI/enrichment — **chosen.**

**Rationale:** Go's static binaries, goroutine scheduler, and single-binary deploys make it ideal for `alert-gateway` (high-alert fanout) and `case-service` (concurrent case updates). Python's AI ecosystem (Vertex AI SDK, pydantic, asyncio) gives a faster iteration cycle on the enrichment and LLM pipeline. Service boundaries are defined by explicit message schemas on Pub/Sub, so each language is isolated behind its contract — no cross-language RPC in the hot path.

**Risks / follow-ups:** Two language toolchains in CI; mitigated by keeping Go tooling (golangci-lint, go test) and Python tooling (ruff, pytest, mypy) in separate CI job groups that mirror each other structurally.

---

## ADR-013 — Message bus: GCP Pub/Sub (NOT Kafka)

**Status:** Accepted · **Date:** 2026-06-30

**Context:** The Sentinel pipeline requires an async queue between alert-gateway → enrichment → masking → llm-orchestrator → case-service. Two realistic options: GCP Pub/Sub (managed, no ops) and Apache Kafka (self-hosted or Confluent Cloud).

**Alternatives considered:**

- Apache Kafka (self-hosted) — rejected for MVP: adds another stateful cluster to operate alongside Elasticsearch. Two stateful clusters for a two-person team is over-engineering at this stage.
- Confluent Cloud (managed Kafka) — rejected: additional vendor + billing overhead; no advantage over Pub/Sub when already on GCP.
- GCP Pub/Sub — **chosen.**

**Rationale:** Pub/Sub is fully managed, integrates with Workload Identity (no broker credentials in pods), and its `at-least-once` delivery + `ack` semantics match the pipeline's requirements. Already on GCP (ADR-007) so no new vendor. For local development, the official `google-cloud-sdk` Pub/Sub emulator runs in docker-compose. The queue is defined behind an interface in each service so swapping to Kafka later requires only a new adapter, not business logic changes.

**Topic layout:**

- `sentinel.alerts` — detection-service → alert-gateway
- `sentinel.incidents` — alert-gateway → enrichment-service
- `sentinel.masked-incidents` — masking-service → llm-orchestrator
- `sentinel.triage-decisions` — llm-orchestrator → case-service
- `sentinel.dlq` — dead-letter for all topics

**Risks / follow-ups:** Pub/Sub ordering is per-message-key (ordering keys); use `incident_id` as the key for masking → llm → case pipeline to preserve causal order.

---

## ADR-014 — Elastic Basic-tier feature availability (initial research)

**Status:** Accepted · **Date:** 2026-06-30

**Context:** CLAUDE.md hard constraint: verify every Elastic feature against the free/Basic tier before depending on it.

**Findings (as of Elasticsearch 8.x):**

| Feature | Tier | Decision |
| --- | --- | --- |
| SIEM detection rules (KQL/EQL/threshold) | **Free/Basic** | ✅ Use — core detection engine |
| Kibana Security app (alerts UI, timeline) | **Free/Basic** | ✅ Use — analyst exploration UI |
| Fleet / Elastic Agent management | **Free/Basic** | ✅ Use — agent management |
| ILM (Index Lifecycle Management) | **Free/Basic** | ✅ Use — 14-day hot tier (ADR-009) |
| GCS snapshot repository | **Free/Basic** | ✅ Use — archive to GCS (ADR-010) |
| `dense_vector` field + kNN search | **Free/Basic** | ✅ Use — RAG vector store fallback |
| ELSER (Elastic Learned Sparse Encoder) | **Platinum** | ❌ Blocked — use `dense_vector` + self-hosted embeddings instead |
| Entity risk scoring | **Platinum** | ❌ Blocked — implement risk scoring in `alert-gateway` as code |
| ML anomaly detection jobs | **Platinum** | ❌ Blocked — use rule-based detection in Basic |
| Searchable snapshots | **Enterprise** | ❌ Blocked — see ADR-010; use raw GCS snapshot + manual restore |
| Cross-cluster replication | **Platinum** | ❌ Not needed at MVP |

**Risks / follow-ups:** The missing risk-scoring feature (normally Platinum) is compensated by deterministic risk scoring in `alert-gateway` using rule severity + CVSS + asset criticality. This is documented in the service design.

---

## Open items to resolve (carry forward)

- Confirm Vertex AI region + data-processing terms (ADR-006).
- Define reverse-map lifecycle/TTL in `masking-service` (ADR-004).
- Legal review: KVKK cross-border transfer with masking + in-region inference (ADR-004).
- Determine regulatory log-retention period and set GCS retention accordingly (ADR-010).
- Implement self-hosted embedding model for RAG (ADR-014 — ELSER blocked).
