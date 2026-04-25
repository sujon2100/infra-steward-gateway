package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/yourorg/infra-steward-gateway/go/evidence_ingester/domain"
)

// TestHealthHandler tests the health endpoint.
func TestHealthHandler(t *testing.T) {
	req := httptest.NewRequest("GET", "/health", nil)
	w := httptest.NewRecorder()
	healthHandler(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp HealthResponse
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp.Status != "healthy" {
		t.Errorf("expected status 'healthy', got %q", resp.Status)
	}

	if resp.Version != version {
		t.Errorf("expected version %q, got %q", version, resp.Version)
	}

	if resp.UptimeSeconds < 0 {
		t.Errorf("uptime should be non-negative, got %f", resp.UptimeSeconds)
	}
}

// TestInfoHandler tests the info endpoint.
func TestInfoHandler(t *testing.T) {
	req := httptest.NewRequest("GET", "/info", nil)
	w := httptest.NewRecorder()
	infoHandler(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp InfoResponse
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp.Service != "InfraSteward Evidence Ingester" {
		t.Errorf("unexpected service name: %q", resp.Service)
	}

	if resp.Version != version {
		t.Errorf("expected version %q, got %q", version, resp.Version)
	}
}

// TestMetricsHandler tests the metrics endpoint.
func TestMetricsHandler(t *testing.T) {
	req := httptest.NewRequest("GET", "/metrics", nil)
	w := httptest.NewRecorder()
	metricsHandler(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	if w.Header().Get("Content-Type") != "text/plain; charset=utf-8" {
		t.Errorf("expected Content-Type text/plain, got %q", w.Header().Get("Content-Type"))
	}

	body := w.Body.String()
	if body == "" {
		t.Error("metrics body should not be empty")
	}

	// Check for Prometheus format markers
	if !(contains(body, "HELP") || contains(body, "TYPE") || contains(body, "ingester_")) {
		t.Error("metrics body does not contain expected Prometheus markers")
	}
}

// TestEvidenceEventTimestampUnmarshal tests that both naive and RFC3339 timestamps are accepted.
func TestEvidenceEventTimestampUnmarshal(t *testing.T) {
	samples := []string{
		`{"timestamp":"2026-03-29T08:34:44.248050","event_type":"WORKFLOW_STARTED","details":{}}`,
		`{"timestamp":"2026-03-29T08:34:44.248050Z","event_type":"WORKFLOW_STARTED","details":{}}`,
	}

	for _, sample := range samples {
		var event domain.EvidenceEvent
		if err := json.NewDecoder(strings.NewReader(sample)).Decode(&event); err != nil {
			t.Fatalf("failed to decode event %q: %v", sample, err)
		}
		if time.Time(event.Timestamp).IsZero() {
			t.Fatalf("expected non-zero timestamp for sample %q", sample)
		}
	}
}

// TestEvidenceEventsHandler tests the evidence events endpoint.
func TestEvidenceEventsHandler(t *testing.T) {
	req := httptest.NewRequest("POST", "/evidence/events", nil)
	w := httptest.NewRecorder()
	evidenceEventsHandler(w, req)

	if w.Code != http.StatusAccepted {
		t.Errorf("expected status 202, got %d", w.Code)
	}

	var resp map[string]string
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if resp["status"] != "accepted" {
		t.Errorf("expected status 'accepted', got %q", resp["status"])
	}
}

// TestEvidenceEventsHandlerMethodNotAllowed tests that non-POST requests are rejected.
func TestEvidenceEventsHandlerMethodNotAllowed(t *testing.T) {
	req := httptest.NewRequest("GET", "/evidence/events", nil)
	w := httptest.NewRecorder()
	evidenceEventsHandler(w, req)

	if w.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected status 405, got %d", w.Code)
	}
}

// Helper function to check if a string contains a substring.
func contains(s, substr string) bool {
	for i := 0; i < len(s)-len(substr)+1; i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
