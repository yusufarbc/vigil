package pubsub

import (
	"context"

	"sentinel/alert-gateway/internal/incident"
)

// AlertSubscriber receives normalized alerts from the sentinel.alerts topic.
type AlertSubscriber interface {
	Subscribe(ctx context.Context, handler func(ctx context.Context, a *incident.Alert) error) error
	Close() error
}

// IncidentPublisher sends formed incidents to the sentinel.incidents topic.
type IncidentPublisher interface {
	Publish(ctx context.Context, inc *incident.Incident) error
	Close() error
}
