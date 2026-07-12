package domain

import (
	"fmt"
	"strings"
	"time"
)

// EvidenceTimestamp is a flexible wrapper around time.Time that accepts
// either fully-qualified RFC3339 timestamps or naive local timestamps.
type EvidenceTimestamp time.Time

// UnmarshalJSON accepts multiple timestamp formats for resilience in mixed clients.
func (t *EvidenceTimestamp) UnmarshalJSON(data []byte) error {
	str := strings.Trim(string(data), `"`)
	if str == "" || str == "null" {
		return nil
	}

	parsers := []string{
		time.RFC3339Nano,
		time.RFC3339,
		"2006-01-02T15:04:05.999999",
		"2006-01-02T15:04:05",
	}

	for _, layout := range parsers {
		if parsed, err := time.Parse(layout, str); err == nil {
			*t = EvidenceTimestamp(parsed.UTC())
			return nil
		}
	}

	return fmt.Errorf("invalid timestamp format: %q", str)
}

// MarshalJSON always outputs RFC3339Nano UTC format for consistency.
func (t EvidenceTimestamp) MarshalJSON() ([]byte, error) {
	ts := time.Time(t).UTC().Format(time.RFC3339Nano)
	return []byte("\"" + ts + "\""), nil
}

// EvidenceEventType represents the type of evidence event.
type EvidenceEventType string

const (
	WorkflowStarted          EvidenceEventType = "WORKFLOW_STARTED"
	PolicyEvaluated          EvidenceEventType = "POLICY_EVALUATED"
	ProviderSelected         EvidenceEventType = "PROVIDER_SELECTED"
	ProviderFailed           EvidenceEventType = "PROVIDER_FAILED"
	WorkflowCompleted        EvidenceEventType = "WORKFLOW_COMPLETED"
	ConsentEvaluated         EvidenceEventType = "CONSENT_EVALUATED"
	DSITransparencyEvaluated EvidenceEventType = "DSI_TRANSPARENCY_EVALUATED"
)

// EvidenceEvent represents an event in the evidence record.
type EvidenceEvent struct {
	Timestamp EvidenceTimestamp      `json:"timestamp"`
	EventType EvidenceEventType      `json:"event_type"`
	Details   map[string]interface{} `json:"details"`
}

// EvidenceRecord represents a complete evidence record.
type EvidenceRecord struct {
	RequestID          string          `json:"request_id"`
	TenantID           string          `json:"tenant_id"`
	Scenario           *string         `json:"scenario,omitempty"`
	ReportID           *string         `json:"report_id,omitempty"`
	ReportType         *string         `json:"report_type,omitempty"`
	Jurisdiction       *string         `json:"jurisdiction,omitempty"`
	Regime             *string         `json:"regime,omitempty"`
	PolicySuiteVersion *string         `json:"policy_suite_version,omitempty"`
	PoliciesApplied    []string        `json:"policies_applied"`
	DecisionOutcome    *string         `json:"decision_outcome,omitempty"`
	ProviderName       *string         `json:"provider_name,omitempty"`
	ProviderMode       *string         `json:"provider_mode,omitempty"`
	RedactionApplied   *bool           `json:"redaction_applied,omitempty"`
	RiskLevel          *string         `json:"risk_level,omitempty"`
	InputHash          *string         `json:"input_hash,omitempty"`
	OutputHash         *string         `json:"output_hash,omitempty"`
	Events             []EvidenceEvent `json:"events"`
	Status             string          `json:"status"`

	// Consent basis for a governed PHI exchange; empty for the banking flow.
	ConsentID     *string  `json:"consent_id,omitempty"`
	PurposeOfUse  *string  `json:"purpose_of_use,omitempty"`
	PHICategories []string `json:"phi_categories,omitempty"`
	DisclosingOrg *string  `json:"disclosing_org,omitempty"`
	ReceivingOrg  *string  `json:"receiving_org,omitempty"`

	// DSI transparency basis (HTI-1, 45 CFR 170.315(b)(11)); empty outside
	// the advisory/predictive-DSI flow.
	DSIID                 *string  `json:"dsi_id,omitempty"`
	DSIOutputType         *string  `json:"dsi_output_type,omitempty"`
	DSIDecisionMakingRole *string  `json:"dsi_decision_making_role,omitempty"`
	DSIMissingAttributes  []string `json:"dsi_missing_attributes,omitempty"`
}

// NewEvidenceRecord creates a new evidence record.
func NewEvidenceRecord(requestID, tenantID string) *EvidenceRecord {
	return &EvidenceRecord{
		RequestID:       requestID,
		TenantID:        tenantID,
		PoliciesApplied: []string{},
		Events:          []EvidenceEvent{},
		Status:          "in_progress",
	}
}

// AddEvent adds an event to the evidence record.
func (r *EvidenceRecord) AddEvent(eventType EvidenceEventType, details map[string]interface{}) {
	event := EvidenceEvent{
		Timestamp: EvidenceTimestamp(time.Now().UTC()),
		EventType: eventType,
		Details:   details,
	}
	r.Events = append(r.Events, event)
}
