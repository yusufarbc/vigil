package incident

import (
	"crypto/sha256"
	"fmt"
	"sort"
	"sync"
	"time"
)

// severityWeight maps severity strings to numeric weights for risk scoring.
var severityWeight = map[string]int{
	"critical": 40,
	"high":     25,
	"medium":   10,
	"low":      3,
}

// window is how long alerts are held before the incident is flushed.
const window = 10 * time.Minute

// Correlator groups related alerts into incidents using a time-windowed,
// key-based strategy. The correlation key is (host+user+top_mitre_tactic).
// Incidents are emitted once the window closes or the alert count threshold is met.
type Correlator struct {
	mu       sync.Mutex
	buckets  map[string]*bucket
	threshold int
}

type bucket struct {
	inc       *Incident
	expiresAt time.Time
}

func NewCorrelator(threshold int) *Correlator {
	return &Correlator{
		buckets:   make(map[string]*bucket),
		threshold: threshold,
	}
}

// Ingest adds an alert to the correlator. Returns a flushed incident if the
// window or threshold was exceeded, otherwise returns nil.
func (c *Correlator) Ingest(a *Alert) *Incident {
	key := correlationKey(a)

	c.mu.Lock()
	defer c.mu.Unlock()

	b, exists := c.buckets[key]
	if !exists {
		inc := &Incident{
			ID:             newID(),
			CreatedAt:      a.Timestamp,
			UpdatedAt:      a.Timestamp,
			Status:         StatusNew,
			CorrelationKey: key,
		}
		b = &bucket{inc: inc, expiresAt: time.Now().Add(window)}
		c.buckets[key] = b
	}

	inc := b.inc
	inc.Alerts = append(inc.Alerts, a)
	inc.AlertCount = len(inc.Alerts)
	inc.UpdatedAt = a.Timestamp
	mergeAlert(inc, a)
	inc.RiskScore = computeRisk(inc)

	if inc.AlertCount >= c.threshold || time.Now().After(b.expiresAt) {
		delete(c.buckets, key)
		return inc
	}
	return nil
}

// Flush returns all open incidents that have expired, removing them from the correlator.
func (c *Correlator) Flush() []*Incident {
	c.mu.Lock()
	defer c.mu.Unlock()

	now := time.Now()
	var out []*Incident
	for key, b := range c.buckets {
		if now.After(b.expiresAt) {
			out = append(out, b.inc)
			delete(c.buckets, key)
		}
	}
	return out
}

func correlationKey(a *Alert) string {
	tactic := ""
	if len(a.MITRETechniqueIDs) > 0 {
		tactic = a.MITRETechniqueIDs[0]
	}
	return fmt.Sprintf("%s|%s|%s", a.HostName, a.UserName, tactic)
}

func mergeAlert(inc *Incident, a *Alert) {
	inc.AffectedHosts = unique(append(inc.AffectedHosts, a.HostName))
	inc.AffectedUsers = unique(append(inc.AffectedUsers, a.UserName))
	if a.SourceIP != "" {
		inc.SourceIPs = unique(append(inc.SourceIPs, a.SourceIP))
	}
	inc.MITRETechniques = unique(append(inc.MITRETechniques, a.MITRETechniqueIDs...))
}

func computeRisk(inc *Incident) int {
	score := 0
	for _, a := range inc.Alerts {
		score += severityWeight[a.Severity]
	}
	// Spread bonus: multiple hosts or techniques raise urgency.
	score += (len(inc.AffectedHosts) - 1) * 5
	score += (len(inc.MITRETechniques) - 1) * 3
	if score > 100 {
		score = 100
	}
	return score
}

func unique(ss []string) []string {
	seen := make(map[string]struct{}, len(ss))
	out := ss[:0]
	for _, s := range ss {
		if _, ok := seen[s]; !ok {
			seen[s] = struct{}{}
			out = append(out, s)
		}
	}
	sort.Strings(out)
	return out
}

func newID() string {
	b := make([]byte, 16)
	h := sha256.New()
	h.Write([]byte(fmt.Sprintf("%d", time.Now().UnixNano())))
	return fmt.Sprintf("%x", h.Sum(nil)[:8])
}
