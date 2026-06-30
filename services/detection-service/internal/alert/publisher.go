package alert

import "context"

// Publisher sends normalized alerts to the message bus.
// The concrete implementation targets GCP Pub/Sub; the interface allows swapping.
type Publisher interface {
	Publish(ctx context.Context, a *Alert) error
	Close() error
}
