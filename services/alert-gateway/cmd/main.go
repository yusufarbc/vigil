package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"
	"time"

	"sentinel/alert-gateway/internal/incident"
	agpubsub "sentinel/alert-gateway/internal/pubsub"

	"go.uber.org/zap"
)

func main() {
	log, _ := zap.NewProduction()
	defer log.Sync() //nolint:errcheck

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	correlator := incident.NewCorrelator(10)

	// Phase 1: no-op stubs. Phase 2 replaces with Pub/Sub adapters.
	sub := &noopSubscriber{}
	pub := &noopPublisher{}

	// Flush expired buckets every 30 s.
	go func() {
		t := time.NewTicker(30 * time.Second)
		defer t.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-t.C:
				for _, inc := range correlator.Flush() {
					inc.Status = incident.StatusPendingTriage
					if err := pub.Publish(ctx, inc); err != nil {
						log.Error("incident publish failed", zap.Error(err))
					}
				}
			}
		}
	}()

	log.Info("alert-gateway starting")
	if err := sub.Subscribe(ctx, func(ctx context.Context, a *incident.Alert) error {
		if inc := correlator.Ingest(a); inc != nil {
			inc.Status = incident.StatusPendingTriage
			return pub.Publish(ctx, inc)
		}
		return nil
	}); err != nil && err != context.Canceled {
		log.Fatal("alert-gateway exited with error", zap.Error(err))
	}
	log.Info("alert-gateway stopped")
}

type noopSubscriber struct{}

func (n *noopSubscriber) Subscribe(_ context.Context, _ func(context.Context, *incident.Alert) error) error {
	return nil
}
func (n *noopSubscriber) Close() error { return nil }

type noopPublisher struct{}

func (n *noopPublisher) Publish(_ context.Context, _ *incident.Incident) error { return nil }
func (n *noopPublisher) Close() error                                           { return nil }

var _ agpubsub.AlertSubscriber = (*noopSubscriber)(nil)
var _ agpubsub.IncidentPublisher = (*noopPublisher)(nil)
