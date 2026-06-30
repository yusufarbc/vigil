package case_

import "time"

// ReviewStatus tracks where a case is in the human-review queue.
type ReviewStatus string

const (
	ReviewPending  ReviewStatus = "pending"
	ReviewApproved ReviewStatus = "approved"
	ReviewRejected ReviewStatus = "rejected"
)

// TriageDecision is a local copy of the schema produced by llm-orchestrator.
type TriageDecision struct {
	IncidentID                string   `json:"incident_id"`
	ModelID                   string   `json:"model_id"`
	SeveritySuggestion        string   `json:"severity_suggestion"`
	MITRETechniquesConfirmed  []string `json:"mitre_techniques_confirmed"`
	FalsePositiveLikelihood   float64  `json:"false_positive_likelihood"`
	Summary                   string   `json:"summary"`
	RecommendedActions        []string `json:"recommended_actions"`
	Confidence                float64  `json:"confidence"`
	Rationale                 string   `json:"rationale"`
	PromptHash                string   `json:"prompt_hash"`
	InputTokens               int      `json:"input_tokens"`
	OutputTokens              int      `json:"output_tokens"`
	LatencyMS                 float64  `json:"latency_ms"`
}

// Case is the analyst-facing security case that wraps a TriageDecision
// and tracks the human-review lifecycle. Stored in Elasticsearch.
type Case struct {
	ID             string          `json:"id"`
	CreatedAt      time.Time       `json:"created_at"`
	UpdatedAt      time.Time       `json:"updated_at"`
	IncidentID     string          `json:"incident_id"`
	Decision       TriageDecision  `json:"decision"`
	ReviewStatus   ReviewStatus    `json:"review_status"`
	ReviewedBy     string          `json:"reviewed_by,omitempty"`
	ReviewedAt     *time.Time      `json:"reviewed_at,omitempty"`
	AnalystNotes   string          `json:"analyst_notes,omitempty"`
	// Unmasked fields are populated by case-service after un-masking via masking-service.
	AffectedHosts  []string        `json:"affected_hosts,omitempty"`
	AffectedUsers  []string        `json:"affected_users,omitempty"`
}
