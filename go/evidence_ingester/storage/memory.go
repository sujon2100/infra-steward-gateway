package storage

import (
	"fmt"
	"sync"

	"github.com/yourorg/infra-steward-gateway/go/evidence_ingester/domain"
)

// Storage interface for evidence records.
type Storage interface {
	Store(record *domain.EvidenceRecord) error
	Get(requestID string) (*domain.EvidenceRecord, error)
	Query(tenantID, scenario *string) ([]*domain.EvidenceRecord, error)
}

// MemoryStorage implements in-memory storage for evidence records.
type MemoryStorage struct {
	mu      sync.RWMutex
	records map[string]*domain.EvidenceRecord
}

// NewMemoryStorage creates a new memory storage instance.
func NewMemoryStorage() *MemoryStorage {
	return &MemoryStorage{
		records: make(map[string]*domain.EvidenceRecord),
	}
}

// Store saves an evidence record.
func (s *MemoryStorage) Store(record *domain.EvidenceRecord) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.records[record.RequestID] = record
	return nil
}

// Get retrieves an evidence record by request ID.
func (s *MemoryStorage) Get(requestID string) (*domain.EvidenceRecord, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	record, exists := s.records[requestID]
	if !exists {
		return nil, fmt.Errorf("record not found: %s", requestID)
	}
	return record, nil
}

// Query retrieves evidence records matching the given filters.
func (s *MemoryStorage) Query(tenantID, scenario *string) ([]*domain.EvidenceRecord, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	var results []*domain.EvidenceRecord
	for _, record := range s.records {
		if tenantID != nil && record.TenantID != *tenantID {
			continue
		}
		if scenario != nil && (record.Scenario == nil || *record.Scenario != *scenario) {
			continue
		}
		results = append(results, record)
	}
	return results, nil
}
