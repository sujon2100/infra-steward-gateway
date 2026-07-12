"""
PHI exchange orchestration for the HIE governance scenario.

Deliberately not routed through WorkflowEngine — that engine assumes an AI
provider step and a supervisory submission, neither of which apply here.
A PHI exchange is just: evaluate consent/purpose policy, record the
consent basis as evidence, return the decision. Small enough that forcing
it through the banking engine's shape would add indirection without
buying anything.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.evidence.models import EvidenceEventType
from app.evidence.service import EvidenceService
from app.policy.models import PHIExchangeRequest
from app.policy.service import PolicyService
from app.workflow.events import EventBus


class PHIExchangeCoordinator:
    def __init__(
        self,
        policy_service: PolicyService,
        evidence_service: EvidenceService,
        event_bus: EventBus | None = None,
    ) -> None:
        self.policy_service = policy_service
        self.evidence_service = evidence_service
        self.event_bus = event_bus or EventBus()

    async def process(self, request: PHIExchangeRequest) -> dict[str, Any]:
        request_id = str(uuid4())

        evidence = self.evidence_service.start_phi_exchange_record(
            disclosing_org=request.disclosing_org,
            receiving_org=request.receiving_org,
            consent_id=request.consent_id,
            purpose_of_use=request.purpose_of_use.value,
            phi_categories=[c.value for c in sorted(request.categories)],
            policy_suite_version=self.policy_service.policy_suite_version,
            request_id=request_id,
        )

        decision = self.policy_service.evaluate_phi_exchange(request)

        evidence = self.evidence_service.add_event(
            evidence,
            EvidenceEventType.CONSENT_EVALUATED,
            {
                "allowed": decision.allowed,
                "reason": decision.reason,
                "policies_applied": decision.policies_applied,
            },
        )

        await self.evidence_service.finalize(
            evidence,
            status="completed" if decision.allowed else "blocked",
            decision_outcome="approved" if decision.allowed else "denied",
        )

        await self.event_bus.publish(
            "phi_exchange.evaluated",
            {
                "request_id": request_id,
                "disclosing_org": request.disclosing_org,
                "receiving_org": request.receiving_org,
                "allowed": decision.allowed,
            },
        )

        decision_dict = decision.dict()
        decision_dict["timestamp"] = decision.timestamp.isoformat()

        return {"request_id": request_id, "decision": decision_dict}
