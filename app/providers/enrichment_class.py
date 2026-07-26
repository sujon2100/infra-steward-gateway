"""
Enrichment classes and fallback strategies for AI providers.

Different AI enrichment activities have different governance implications
and require different fallback behaviour when the provider is unavailable.
Providers declare which class of enrichment they perform and which
fallback strategy the workflow engine should apply on failure. The engine
consults these declarations rather than applying a single uniform fallback
across all providers.

Class taxonomy is described in the thesis Extended Background
(Chapter 2, Table "Five classes of AI enrichment"). This module encodes
the same taxonomy in code so the gateway can enforce per-class fallback
rather than relying on prose.
"""

from __future__ import annotations

from enum import StrEnum


class EnrichmentClass(StrEnum):
    """The kind of AI enrichment a provider performs.

    NARRATIVE: generates explanatory text alongside primary structured data
        (LLM narrative around a report; supplementary to the primary data).

    RISK_CLASSIFICATION: produces a prediction, score, or category from
        the request data (e.g., clinical DSI sepsis risk score, transaction
        risk flag). A missing score changes the caller's decision.

    STRUCTURED_ENRICHMENT: extracts or infers structured metadata
        (categorisations, tags, entity resolution). Field provenance
        must travel with the field.

    REDACTION: removes sensitive fields before onward transmission
        (e.g., PHI redaction on export). Silent failure means over-
        disclosure --- a hard privacy failure.

    TRANSLATION: cross-language reporting. Provenance of translation
        (which model, which pass) must be recorded.
    """

    NARRATIVE = "narrative"
    RISK_CLASSIFICATION = "risk_classification"
    STRUCTURED_ENRICHMENT = "structured_enrichment"
    REDACTION = "redaction"
    TRANSLATION = "translation"


class FallbackStrategy(StrEnum):
    """What the workflow engine should do when this provider fails.

    DROP_AND_SIGNAL: omit the enrichment for this request, return the
        response with `status: fallback` and the intended `provider_used`,
        record a PROVIDER_FALLBACK_APPLIED event in evidence. Primary
        data flows through unchanged. Appropriate for NARRATIVE class,
        where the enrichment is supplementary to the primary data.

    FAIL_CLOSED: block the request, return the response with
        `status: blocked_provider_failure` and no result, record a
        PROVIDER_FALLBACK_BLOCKED event in evidence. Appropriate for
        RISK_CLASSIFICATION and REDACTION classes, where silently
        omitting the enrichment would either change a decision the
        caller depends on (risk score) or emit under-protected data
        (missing redaction).
    """

    DROP_AND_SIGNAL = "drop_and_signal"
    FAIL_CLOSED = "fail_closed"
