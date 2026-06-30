package alert

import "time"

// Severity maps to the severity field in detection rules.
type Severity string

const (
	SeverityCritical Severity = "critical"
	SeverityHigh     Severity = "high"
	SeverityMedium   Severity = "medium"
	SeverityLow      Severity = "low"
)

// Alert is the normalized event emitted by detection-service to the sentinel.alerts topic.
// It is the contract between detection-service and alert-gateway.
type Alert struct {
	ID                  string            `json:"id"`
	Timestamp           time.Time         `json:"timestamp"`
	RuleID              string            `json:"rule_id"`
	RuleName            string            `json:"rule_name"`
	Severity            Severity          `json:"severity"`
	MITRETechniqueIDs   []string          `json:"mitre_technique_ids"`
	MITRETechniqueNames []string          `json:"mitre_technique_names"`
	SourceIndex         string            `json:"source_index"`
	RawEventID          string            `json:"raw_event_id"`
	HostName            string            `json:"host_name"`
	UserName            string            `json:"user_name"`
	SourceIP            string            `json:"source_ip,omitempty"`
	ProcessName         string            `json:"process_name,omitempty"`
	EventDetails        map[string]string `json:"event_details,omitempty"`
}
