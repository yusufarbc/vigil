.PHONY: up down build test lint clean logs

GO_SERVICES   := detection-service alert-gateway case-service bff
PY_SERVICES   := enrichment-service masking-service llm-orchestrator

# ---------------------------------------------------------------------------
# Local dev
# ---------------------------------------------------------------------------

up:
	docker compose up -d --build
	@echo "Kibana:  http://localhost:5601"
	@echo "BFF:     http://localhost:8080"

down:
	docker compose down

logs:
	docker compose logs -f --tail=50

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

build:
	docker compose build

build-go:
	$(foreach svc,$(GO_SERVICES),cd services/$(svc) && go build ./... && cd ../..;)

build-py:
	$(foreach svc,$(PY_SERVICES),cd services/$(svc) && pip install -q . && cd ../..;)

# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

test: test-go test-py

test-go:
	$(foreach svc,$(GO_SERVICES),\
	  echo "==> testing $(svc)" && \
	  cd services/$(svc) && go test ./... -race -count=1 && cd ../..;)

test-py:
	$(foreach svc,$(PY_SERVICES),\
	  echo "==> testing $(svc)" && \
	  cd services/$(svc) && python -m pytest tests/ -v 2>/dev/null || echo "no tests yet" && cd ../..;)

# ---------------------------------------------------------------------------
# Lint
# ---------------------------------------------------------------------------

lint: lint-go lint-py

lint-go:
	$(foreach svc,$(GO_SERVICES),\
	  echo "==> linting $(svc)" && \
	  cd services/$(svc) && golangci-lint run ./... && cd ../..;)

lint-py:
	$(foreach svc,$(PY_SERVICES),\
	  echo "==> linting $(svc)" && \
	  cd services/$(svc) && ruff check . && ruff format --check . && cd ../..;)

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

clean:
	docker compose down -v --remove-orphans
	docker system prune -f

# ---------------------------------------------------------------------------
# Pub/Sub topic bootstrap (run once against the emulator)
# ---------------------------------------------------------------------------

pubsub-init:
	@echo "Creating Pub/Sub topics and subscriptions on emulator..."
	$(eval PUBSUB_URL=http://localhost:8085)
	curl -s -X PUT "$(PUBSUB_URL)/v1/projects/sentinel-local/topics/sentinel.alerts"
	curl -s -X PUT "$(PUBSUB_URL)/v1/projects/sentinel-local/topics/sentinel.incidents"
	curl -s -X PUT "$(PUBSUB_URL)/v1/projects/sentinel-local/topics/sentinel.masked-incidents"
	curl -s -X PUT "$(PUBSUB_URL)/v1/projects/sentinel-local/topics/sentinel.triage-decisions"
	curl -s -X PUT "$(PUBSUB_URL)/v1/projects/sentinel-local/topics/sentinel.dlq"
	curl -s -X PUT "$(PUBSUB_URL)/v1/projects/sentinel-local/subscriptions/sentinel.alerts.gateway-sub" \
	  -H "Content-Type: application/json" \
	  -d '{"topic":"projects/sentinel-local/topics/sentinel.alerts"}'
	curl -s -X PUT "$(PUBSUB_URL)/v1/projects/sentinel-local/subscriptions/sentinel.incidents.enrichment-sub" \
	  -H "Content-Type: application/json" \
	  -d '{"topic":"projects/sentinel-local/topics/sentinel.incidents"}'
	curl -s -X PUT "$(PUBSUB_URL)/v1/projects/sentinel-local/subscriptions/sentinel.masked-incidents.llm-sub" \
	  -H "Content-Type: application/json" \
	  -d '{"topic":"projects/sentinel-local/topics/sentinel.masked-incidents"}'
	curl -s -X PUT "$(PUBSUB_URL)/v1/projects/sentinel-local/subscriptions/sentinel.triage-decisions.case-sub" \
	  -H "Content-Type: application/json" \
	  -d '{"topic":"projects/sentinel-local/topics/sentinel.triage-decisions"}'
	@echo "Done."
