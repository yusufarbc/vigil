package elastic

import "context"

// RawAlert is the raw document returned from the Elasticsearch alerts index
// (.alerts-security.alerts-*). Only the fields needed for normalization are mapped.
type RawAlert struct {
	ID        string            `json:"_id"`
	Source    map[string]any    `json:"_source"`
}

// Client abstracts Elasticsearch reads so the service is not coupled to the SDK.
type Client interface {
	// SearchAlerts returns at most limit un-processed security alerts ordered by timestamp asc.
	SearchAlerts(ctx context.Context, afterTimestamp string, limit int) ([]*RawAlert, error)
	Close() error
}
