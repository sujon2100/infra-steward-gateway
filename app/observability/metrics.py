"""Prometheus metrics for InfraSteward gateway."""

from prometheus_client import Counter, Histogram

# Request-level metrics
gateway_requests_total = Counter(
    "gateway_requests_total",
    "Total number of gateway requests",
    ["method", "endpoint", "status"],
)

gateway_request_latency_seconds = Histogram(
    "gateway_request_latency_seconds",
    "Gateway request latency in seconds",
    ["method", "endpoint"],
)

# Governance metrics
gateway_policy_outcomes_total = Counter(
    "gateway_policy_outcomes_total",
    "Policy decision outcomes by tenant and scenario",
    ["tenant_id", "scenario", "policy_outcome"],
)

gateway_provider_outcomes_total = Counter(
    "gateway_provider_outcomes_total",
    "AI provider outcomes by tenant and scenario",
    ["tenant_id", "scenario", "provider_status"],
)

# Supervisory reporting metrics
gateway_supervisory_submissions_total = Counter(
    "gateway_supervisory_submissions_total",
    "Reports forwarded to the supervisory / tax reporting service",
    ["tenant_id", "scenario", "submission_status"],
)
