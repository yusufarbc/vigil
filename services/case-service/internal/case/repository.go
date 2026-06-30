package case_

import "context"

// Repository abstracts case persistence. Concrete implementation stores in Elasticsearch.
type Repository interface {
	Create(ctx context.Context, c *Case) error
	Update(ctx context.Context, c *Case) error
	GetByID(ctx context.Context, id string) (*Case, error)
	ListPendingReview(ctx context.Context, limit int) ([]*Case, error)
}
