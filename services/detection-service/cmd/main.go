package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"
	"time"

	internal "sentinel/detection-service/internal"
	"sentinel/detection-service/internal/alert"
	"sentinel/detection-service/internal/elastic"

	"go.uber.org/zap"
)

func main() {
	log, _ := zap.NewProduction()
	defer log.Sync() //nolint:errcheck

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	// Phase 1: wire no-op stubs so the binary compiles and exits cleanly.
	// Phase 2 replaces these with concrete ES + Pub/Sub adapters.
	svc := internal.New(
		&noopESClient{},
		&noopPublisher{},
		log,
		30*time.Second,
	)

	log.Info("detection-service starting")
	if err := svc.Run(ctx); err != nil && err != context.Canceled {
		log.Fatal("detection-service exited with error", zap.Error(err))
	}
	log.Info("detection-service stopped")
}

type noopESClient struct{}

func (n *noopESClient) SearchAlerts(_ context.Context, _ string, _ int) ([]*elastic.RawAlert, error) {
	return nil, nil
}
func (n *noopESClient) Close() error { return nil }

type noopPublisher struct{}

func (n *noopPublisher) Publish(_ context.Context, _ *alert.Alert) error { return nil }
func (n *noopPublisher) Close() error                                     { return nil }
