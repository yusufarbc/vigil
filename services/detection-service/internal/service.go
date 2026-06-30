package internal

import (
	"context"
	"time"

	"sentinel/detection-service/internal/alert"
	"sentinel/detection-service/internal/elastic"

	"go.uber.org/zap"
)

// DetectionService polls Elasticsearch for new security alerts, normalizes them
// according to the rule catalogue, and publishes them to the alert bus.
type DetectionService struct {
	es        elastic.Client
	publisher alert.Publisher
	log       *zap.Logger
	pollEvery time.Duration
}

func New(es elastic.Client, pub alert.Publisher, log *zap.Logger, pollEvery time.Duration) *DetectionService {
	return &DetectionService{
		es:        es,
		publisher: pub,
		log:       log,
		pollEvery: pollEvery,
	}
}

// Run polls ES in a loop until ctx is cancelled.
func (s *DetectionService) Run(ctx context.Context) error {
	ticker := time.NewTicker(s.pollEvery)
	defer ticker.Stop()

	var lastSeen string

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-ticker.C:
			raw, err := s.es.SearchAlerts(ctx, lastSeen, 100)
			if err != nil {
				s.log.Warn("ES poll failed", zap.Error(err))
				continue
			}
			for _, r := range raw {
				a := normalize(r)
				if err := s.publisher.Publish(ctx, a); err != nil {
					s.log.Error("publish failed", zap.String("raw_id", r.ID), zap.Error(err))
					continue
				}
				lastSeen = a.Timestamp.Format(time.RFC3339Nano)
			}
		}
	}
}

// normalize converts a raw Elasticsearch alert document to a typed Alert.
// Field mapping follows the Elastic Security ECS schema.
func normalize(r *elastic.RawAlert) *alert.Alert {
	src := r.Source

	getString := func(key string) string {
		if v, ok := src[key]; ok {
			if s, ok := v.(string); ok {
				return s
			}
		}
		return ""
	}

	ts := time.Now()
	if raw := getString("@timestamp"); raw != "" {
		if parsed, err := time.Parse(time.RFC3339, raw); err == nil {
			ts = parsed
		}
	}

	sev := alert.SeverityMedium
	switch getString("kibana.alert.severity") {
	case "critical":
		sev = alert.SeverityCritical
	case "high":
		sev = alert.SeverityHigh
	case "low":
		sev = alert.SeverityLow
	}

	return &alert.Alert{
		ID:          r.ID,
		Timestamp:   ts,
		RuleID:      getString("kibana.alert.rule.parameters.rule_id"),
		RuleName:    getString("kibana.alert.rule.name"),
		Severity:    sev,
		SourceIndex: getString("kibana.alert.rule.parameters.index"),
		RawEventID:  r.ID,
		HostName:    getString("host.name"),
		UserName:    getString("user.name"),
		SourceIP:    getString("source.ip"),
		ProcessName: getString("process.name"),
	}
}
