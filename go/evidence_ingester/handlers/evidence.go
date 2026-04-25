package handlers

import (
	"encoding/json"
	"log"
	"net/http"
	"strings"

	"github.com/yourorg/infra-steward-gateway/go/evidence_ingester/domain"
	"github.com/yourorg/infra-steward-gateway/go/evidence_ingester/storage"
)

// EvidenceHandler handles evidence-related HTTP requests.
type EvidenceHandler struct {
	storage          storage.Storage
	incrementCounter func()
}

// NewEvidenceHandler creates a new evidence handler.
func NewEvidenceHandler(storage storage.Storage, incrementCounter func()) *EvidenceHandler {
	return &EvidenceHandler{storage: storage, incrementCounter: incrementCounter}
}

// HandleEvents handles POST /evidence/events.
func (h *EvidenceHandler) HandleEvents(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var record domain.EvidenceRecord
	if err := json.NewDecoder(r.Body).Decode(&record); err != nil {
		log.Printf("error decoding evidence record: %v", err)
		http.Error(w, "invalid JSON", http.StatusBadRequest)
		return
	}

	if record.RequestID == "" {
		http.Error(w, "request_id is required", http.StatusBadRequest)
		return
	}

	if err := h.storage.Store(&record); err != nil {
		log.Printf("error storing evidence record: %v", err)
		http.Error(w, "internal server error", http.StatusInternalServerError)
		return
	}

	// Increment the events counter
	if h.incrementCounter != nil {
		h.incrementCounter()
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusAccepted)
	response := map[string]string{
		"status":  "accepted",
		"message": "evidence record stored",
	}
	json.NewEncoder(w).Encode(response)
}

// HandleGetByID handles GET /evidence/{request_id}.
func (h *EvidenceHandler) HandleGetByID(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Extract request_id from URL path
	path := strings.TrimPrefix(r.URL.Path, "/evidence/")
	if path == "" || strings.Contains(path, "/") {
		http.Error(w, "invalid request ID", http.StatusBadRequest)
		return
	}

	record, err := h.storage.Get(path)
	if err != nil {
		log.Printf("error retrieving evidence record: %v", err)
		http.Error(w, "record not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(record)
}

// HandleQuery handles GET /evidence (with query parameters).
func (h *EvidenceHandler) HandleQuery(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	tenantID := r.URL.Query().Get("tenant_id")
	scenario := r.URL.Query().Get("scenario")

	var tenantIDPtr, scenarioPtr *string
	if tenantID != "" {
		tenantIDPtr = &tenantID
	}
	if scenario != "" {
		scenarioPtr = &scenario
	}

	records, err := h.storage.Query(tenantIDPtr, scenarioPtr)
	if err != nil {
		log.Printf("error querying evidence records: %v", err)
		http.Error(w, "internal server error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(records)
}
