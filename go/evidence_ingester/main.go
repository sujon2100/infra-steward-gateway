package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"sync/atomic"
	"time"

	"github.com/yourorg/infra-steward-gateway/go/evidence_ingester/handlers"
	"github.com/yourorg/infra-steward-gateway/go/evidence_ingester/storage"
)

const (
	version     = "0.1.0"
	defaultPort = 8081
)

var startTime = time.Now()

// Simple metrics counters
var (
	ingesterEventsTotal int64
)

// HealthResponse represents the health check response.
type HealthResponse struct {
	Status        string  `json:"status"`
	Version       string  `json:"version"`
	UptimeSeconds float64 `json:"uptime_seconds"`
	Timestamp     string  `json:"timestamp"`
}

// InfoResponse represents the info endpoint response.
type InfoResponse struct {
	Service       string  `json:"service"`
	Version       string  `json:"version"`
	Port          int     `json:"port"`
	UptimeSeconds float64 `json:"uptime_seconds"`
}

// healthHandler handles GET /health requests.
func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)

	response := HealthResponse{
		Status:        "healthy",
		Version:       version,
		UptimeSeconds: time.Since(startTime).Seconds(),
		Timestamp:     time.Now().UTC().Format(time.RFC3339),
	}

	if err := json.NewEncoder(w).Encode(response); err != nil {
		log.Printf("error encoding health response: %v", err)
	}
}

// infoHandler handles GET /info requests.
func infoHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)

	response := InfoResponse{
		Service:       "InfraSteward Evidence Ingester",
		Version:       version,
		Port:          defaultPort,
		UptimeSeconds: time.Since(startTime).Seconds(),
	}

	if err := json.NewEncoder(w).Encode(response); err != nil {
		log.Printf("error encoding info response: %v", err)
	}
}

// rootHandler handles GET / requests.
func rootHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)

	response := map[string]interface{}{
		"service": "InfraSteward Evidence Ingester",
		"version": version,
		"endpoints": map[string]string{
			"health":                  "/health",
			"info":                    "/info",
			"metrics":                 "/metrics",
			"evidence_events_post":    "/evidence/events",
			"evidence_get_by_request": "/evidence/{request_id}",
			"evidence_query":          "/evidence?tenant_id=...&scenario=...",
		},
	}

	if err := json.NewEncoder(w).Encode(response); err != nil {
		log.Printf("error encoding root response: %v", err)
	}
}

// metricsHandler handles GET /metrics requests (Prometheus format).
func metricsHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(http.StatusOK)

	eventsTotal := atomic.LoadInt64(&ingesterEventsTotal)

	metrics := fmt.Sprintf(`# HELP ingester_events_total Total number of events received
# TYPE ingester_events_total counter
ingester_events_total %d

# HELP ingester_response_latency_seconds Response latency in seconds
# TYPE ingester_response_latency_seconds histogram
ingester_response_latency_seconds_bucket{le="+Inf"} 0
ingester_response_latency_seconds_sum 0
ingester_response_latency_seconds_count 0
`, eventsTotal)
	fmt.Fprint(w, metrics)
}

// evidenceEventsHandler handles POST /evidence/events (placeholder).
func evidenceEventsHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusAccepted)

	response := map[string]string{
		"status":  "accepted",
		"message": "event queued for processing",
	}

	if err := json.NewEncoder(w).Encode(response); err != nil {
		log.Printf("error encoding evidence response: %v", err)
	}
}

// DEPRECATED: This function is replaced by handlers.EvidenceHandler

// loggingMiddleware logs incoming requests.
func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		log.Printf("%s %s %s", r.Method, r.RequestURI, r.RemoteAddr)
		next.ServeHTTP(w, r)
		log.Printf("completed in %v", time.Since(start))
	})
}

func main() {
	// Initialize storage
	store := storage.NewMemoryStorage()

	// Initialize handlers
	incrementCounter := func() {
		atomic.AddInt64(&ingesterEventsTotal, 1)
	}
	evidenceHandler := handlers.NewEvidenceHandler(store, incrementCounter)

	// Create router
	mux := http.NewServeMux()

	// Register handlers
	mux.HandleFunc("/", rootHandler)
	mux.HandleFunc("/health", healthHandler)
	mux.HandleFunc("/info", infoHandler)
	mux.HandleFunc("/metrics", metricsHandler)
	mux.HandleFunc("/evidence/events", evidenceHandler.HandleEvents)
	mux.HandleFunc("/evidence/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet && strings.HasSuffix(r.URL.Path, "/evidence/") {
			evidenceHandler.HandleQuery(w, r)
		} else {
			evidenceHandler.HandleGetByID(w, r)
		}
	})

	// Wrap with logging middleware
	handler := loggingMiddleware(mux)

	// Start server
	addr := fmt.Sprintf(":%d", defaultPort)
	log.Printf("InfraSteward Evidence Ingester v%s starting on %s", version, addr)
	if err := http.ListenAndServe(addr, handler); err != nil && err != http.ErrServerClosed {
		log.Printf("server error: %v", err)
		os.Exit(1)
	}
}
