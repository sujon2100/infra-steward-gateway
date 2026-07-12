"""
Predictive DSI advisory orchestration (HTI-1, 45 CFR 170.315(b)(11)).

This is the "governed AI-influenced output" checkpoint: before the
provider actually runs, the DSI registration is checked for the
transparency attributes HTI-1 requires at the point of use. If they're
missing, the provider never gets invoked - there's no reason to spend an
inference call on an output that can't be finalized anyway.

No per-DSI provider routing in this pass; every request goes through
whatever provider ProviderRegistry treats as the default. A dsi_id only
identifies which registration to check, not which model actually runs.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.evidence.models import EvidenceEventType
from app.evidence.service import EvidenceService
from app.policy.dsi_models import DSIAdvisoryRequest
from app.policy.service import PolicyService
from app.providers.registry import ProviderRegistry
from app.workflow.events import EventBus
from app.workflow.request_metadata import RequestMetadata


class DSIAdvisoryCoordinator:
    def __init__(
        self,
        policy_service: PolicyService,
        evidence_service: EvidenceService,
        provider_registry: ProviderRegistry,
        event_bus: EventBus | None = None,
    ) -> None:
        self.policy_service = policy_service
        self.evidence_service = evidence_service
        self.provider_registry = provider_registry
        self.event_bus = event_bus or EventBus()

    async def process(self, request: DSIAdvisoryRequest) -> dict[str, Any]:
        request_id = str(uuid4())

        evidence = self.evidence_service.start_dsi_advisory_record(
            requesting_org=request.requesting_org,
            dsi_id=request.dsi_id,
            encounter_id=request.encounter_id,
            policy_suite_version=self.policy_service.policy_suite_version,
            request_id=request_id,
        )

        decision = self.policy_service.evaluate_dsi_output(request)

        evidence = self.evidence_service.record_dsi_transparency_basis(
            evidence,
            output_type=decision.output_type.value if decision.output_type else None,
            decision_making_role=(
                decision.decision_making_role.value if decision.decision_making_role else None
            ),
            missing_attributes=decision.missing_attributes,
        )

        evidence = self.evidence_service.add_event(
            evidence,
            EvidenceEventType.DSI_TRANSPARENCY_EVALUATED,
            {
                "allowed": decision.allowed,
                "reason": decision.reason,
                "policies_applied": decision.policies_applied,
                "missing_attributes": decision.missing_attributes,
            },
        )

        advisory_output: dict[str, Any] | None = None
        status = "blocked"
        decision_outcome = "denied"

        if decision.allowed:
            metadata = RequestMetadata(
                request_id=request_id,
                tenant_id=request.requesting_org,
                scenario="dsi_advisory",
                report_id=request.encounter_id,
            )
            provider = self.provider_registry.get(None)

            try:
                advisory_output = await provider.generate_enrichment(metadata, request.payload)
                evidence = self.evidence_service.add_event(
                    evidence,
                    EvidenceEventType.PROVIDER_SELECTED,
                    {"provider": provider.__class__.__name__},
                )
                status = "completed"
                decision_outcome = "approved"
            except Exception as exc:
                evidence = self.evidence_service.add_event(
                    evidence,
                    EvidenceEventType.PROVIDER_FAILED,
                    {"error": str(exc)},
                )
                status = "fallback"
                decision_outcome = "provider_failure"

        await self.evidence_service.finalize(
            evidence,
            status=status,
            decision_outcome=decision_outcome,
        )

        await self.event_bus.publish(
            "dsi_advisory.evaluated",
            {
                "request_id": request_id,
                "dsi_id": request.dsi_id,
                "requesting_org": request.requesting_org,
                "allowed": decision.allowed,
            },
        )

        decision_dict = decision.dict()
        decision_dict["timestamp"] = decision.timestamp.isoformat()

        return {
            "request_id": request_id,
            "decision": decision_dict,
            "advisory_output": advisory_output,
        }
