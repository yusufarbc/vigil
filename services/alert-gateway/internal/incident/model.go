package incident

import "time"

// Status tracks where an incident is in the triage lifecycle.
type Status string

const (
	StatusNew            Status = "new"
	StatusPendingTriage  Status = "pending_triage"
	StatusTriaged        Status = "triaged"
	StatusClosed         Status = "closed"
)

// Alert is a local copy of the normalized alert schema produced by detection-service.
// Kept local to avoid a shared-library dependency between services.
type Alert struct {
	ID                  string            `json:"id"`
	Timestamp           time.Time         `json:"timestamp"`
	RuleID              string            `json:"rule_id"`
	RuleName            string            `json:"rule_name"`
	Severity            string            `json:"severity"`
	MITRETechniqueIDs   []string          `json:"mitre_technique_ids"`
	MITRETechniqueNames []string          `json:"mitre_technique_names"`
	HostName            string            `json:"host_name"`
	UserName            string            `json:"user_name"`
	SourceIP            string            `json:"source_ip,omitempty"`
	ProcessName         string            `json:"process_name,omitempty"`
	EventDetails        map[string]string `json:"event_details,omitempty"`
}

// Incident is the aggregated security event published to sentinel.incidents.
// It is the contract between alert-gateway and enrichment-service.
type Incident struct {
	ID               string    `json:"id"`
	CreatedAt        time.Time `json:"created_at"`
	UpdatedAt        time.Time `json:"updated_at"`
	Alerts           []*Alert  `json:"alerts"`
	AlertCount       int       `json:"alert_count"`
	AffectedHosts    []string  `json:"affected_hosts"`
	AffectedUsers    []string  `json:"affected_users"`
	SourceIPs        []string  `json:"source_ips"`
	MITRETechniques  []string  `json:"mitre_techniques"`
	RiskScore        int       `json:"risk_score"`
	Status           Status    `json:"status"`
	CorrelationKey   string    `json:"correlation_key"`
}
