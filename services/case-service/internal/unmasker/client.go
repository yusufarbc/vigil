package unmasker

import "context"

// Client calls masking-service to reverse tokens back to plaintext.
// Only case-service uses this — masking-service is the source of truth for PII.
type Client interface {
	Unmask(ctx context.Context, incidentID, token string) (string, error)
	DeleteMap(ctx context.Context, incidentID string) error
}
