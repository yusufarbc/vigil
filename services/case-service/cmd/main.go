package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"

	case_ "sentinel/case-service/internal/case"
	"sentinel/case-service/internal/unmasker"

	"go.uber.org/zap"
)

func main() {
	log, _ := zap.NewProduction()
	defer log.Sync() //nolint:errcheck

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	// Phase 1: no-op stubs. Phase 2 replaces with ES repository + HTTP unmasker + Pub/Sub.
	_ = &noopRepository{}
	_ = &noopUnmasker{}

	log.Info("case-service starting")
	<-ctx.Done()
	log.Info("case-service stopped")
}

type noopRepository struct{}

func (n *noopRepository) Create(_ context.Context, _ *case_.Case) error          { return nil }
func (n *noopRepository) Update(_ context.Context, _ *case_.Case) error          { return nil }
func (n *noopRepository) GetByID(_ context.Context, _ string) (*case_.Case, error) { return nil, nil }
func (n *noopRepository) ListPendingReview(_ context.Context, _ int) ([]*case_.Case, error) {
	return nil, nil
}

type noopUnmasker struct{}

func (n *noopUnmasker) Unmask(_ context.Context, _, _ string) (string, error) { return "", nil }
func (n *noopUnmasker) DeleteMap(_ context.Context, _ string) error            { return nil }

var _ case_.Repository = (*noopRepository)(nil)
var _ unmasker.Client = (*noopUnmasker)(nil)
