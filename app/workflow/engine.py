"""
Workflow engine implementation for Phase 3.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4

from app.evidence.models import EvidenceEventType
from app.evidence.service import EvidenceService
from app.observability.metrics import (
    gateway_policy_outcomes_total,
    gateway_provider_outcomes_total,
)
from app.policy.models import PolicyDecision
from app.policy.service import PolicyService
from app.providers.base import AbstractAIProvider
from app.providers.registry import ProviderRegistry
from app.supervisory.service import SupervisoryReportingService
from app.tenants.context_manager import TenantContextManager
from app.workflow.events import EventBus
from app.workflow.request_metadata import RequestMetadata


class ReportRequest(dict[str, Any]):
    pass


class WorkflowEngine:
    def __init__(
        self,
        policy_service: PolicyService,
        evidence_service: EvidenceService,
        ai_provider: AbstractAIProvider | None = None,
        provider_registry: ProviderRegistry | None = None,
        tenant_context_manager: TenantContextManager | None = None,
        supervisory_service: SupervisoryReportingService | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        if provider_registry is None and ai_provider is None:
            raise ValueError(
                "WorkflowEngine requires either an ai_provider or a provider_registry"
            )

        if provider_registry is None:
            assert ai_provider is not None
            provider_registry = ProviderRegistry(default_name="stub_a")
            provider_registry.register("stub_a", ai_provider)

        self.policy_service = policy_service
        self.evidence_service = evidence_service
        self.provider_registry = provider_registry
        self.ai_provider = ai_provider or provider_registry.get(provider_registry.default_name)
        self.tenant_context_manager = tenant_context_manager or TenantContextManager()
        self.supervisory_service = supervisory_service or SupervisoryReportingService()
        self.event_bus = event_bus or EventBus()

    @staticmethod
    def _sha256_hash(data: Any) -> str:
        payload_bytes = json.dumps(data, sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload_bytes).hexdigest()

    async def process_report(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = str(uuid4())

        # Step 1: resolve tenant context (the first thing in the diagram).
        tenant_context = self.tenant_context_manager.resolve(request["tenant_id"])
        # If the caller did not supply a jurisdiction explicitly, default to
        # the tenant's home jurisdiction from the resolved context.
        effective_jurisdiction = request.get("jurisdiction") or tenant_context.jurisdiction

        metadata = RequestMetadata(
            request_id=request_id,
            tenant_id=tenant_context.tenant_id,
            scenario=request.get("scenario"),
            report_id=request.get("report_id"),
            report_type=request.get("report_type"),
            jurisdiction=effective_jurisdiction,
            regime=request.get("regime"),
            user_id=request.get("user_id"),
        )

        await self.event_bus.publish(
            "tenant.resolved",
            {
                "request_id": request_id,
                "tenant_id": tenant_context.tenant_id,
                "display_name": tenant_context.display_name,
                "policy_scope": tenant_context.policy_scope,
                "jurisdiction": tenant_context.jurisdiction,
            },
        )

        evidence = self.evidence_service.start_record(
            tenant_id=metadata.tenant_id,
            scenario=metadata.scenario,
            report_id=metadata.report_id,
            report_type=metadata.report_type,
            jurisdiction=metadata.jurisdiction,
            regime=metadata.regime,
            policy_suite_version=None,
            request_id=request_id,
        )

        # Step 2: policy evaluation, now including jurisdiction.
        decision: PolicyDecision = self.policy_service.evaluate(
            tenant_id=metadata.tenant_id,
            scenario=metadata.scenario,
            report_type=metadata.report_type,
            jurisdiction=metadata.jurisdiction,
        )

        evidence = self.evidence_service.add_event(
            evidence,
            EvidenceEventType.POLICY_EVALUATED,
            {
                "allowed": decision.allowed,
                "reason": decision.reason,
                "policies_applied": decision.policies_applied,
                "policy_suite_version": decision.policy_suite_version,
            },
        )

        response_payload: dict[str, Any] = {"request_id": request_id, "tenant_id": metadata.tenant_id}
        policy_decision_dict = decision.dict()
        policy_decision_dict["timestamp"] = decision.timestamp.isoformat()
        response_payload["policy_decision"] = policy_decision_dict

        policy_outcome_label = "allowed" if decision.allowed else "denied"
        gateway_policy_outcomes_total.labels(
            tenant_id=metadata.tenant_id,
            scenario=metadata.scenario or "unknown",
            policy_outcome=policy_outcome_label,
        ).inc()

        await self.event_bus.publish(
            "policy.evaluated",
            {
                "request_id": request_id,
                "tenant_id": metadata.tenant_id,
                "allowed": decision.allowed,
                "selected_provider": decision.selected_provider,
                "reason": decision.reason,
            },
        )

        if not decision.allowed:
            gateway_provider_outcomes_total.labels(
                tenant_id=metadata.tenant_id,
                scenario=metadata.scenario or "unknown",
                provider_status="none",
            ).inc()

            evidence = await self.evidence_service.finalize(
                evidence,
                status="blocked",
                decision_outcome="denied",
            )
            await self.event_bus.publish(
                "workflow.completed",
                {"request_id": request_id, "status": "blocked"},
            )
            response_payload.update(
                {
                    "provider_used": None,
                    "status": "blocked",
                    "result": None,
                }
            )
            return response_payload

        input_hash = self._sha256_hash(request.get("payload", {}))

        selected_provider = self.provider_registry.get(decision.selected_provider)
        selected_provider_name = decision.selected_provider or self.provider_registry.default_name

        # Provider has been selected by the routing layer — publish the event
        # now so subscribers see the selection regardless of whether the
        # subsequent invocation succeeds or falls back.
        await self.event_bus.publish(
            "provider.selected",
            {
                "request_id": request_id,
                "tenant_id": metadata.tenant_id,
                "provider": selected_provider.__class__.__name__,
                "provider_name": selected_provider_name,
            },
        )

        try:
            enriched = await selected_provider.generate_enrichment(
                metadata, request.get("payload", {})
            )

            evidence = self.evidence_service.add_event(
                evidence,
                EvidenceEventType.PROVIDER_SELECTED,
                {
                    "provider": selected_provider.__class__.__name__,
                    "provider_name": selected_provider_name,
                    "provider_mode": "stub",
                },
            )

            output_hash = self._sha256_hash(enriched)

            # Step 4: dispatch enriched report to the simulated
            # supervisory / tax reporting service.
            supervisory_ack = await self.supervisory_service.submit_report(
                metadata, enriched
            )
            await self.event_bus.publish(
                "supervisory.submitted",
                {
                    "request_id": request_id,
                    "tenant_id": metadata.tenant_id,
                    "endpoint": supervisory_ack["endpoint"],
                    "accepted": supervisory_ack["accepted"],
                },
            )

            evidence = await self.evidence_service.finalize(
                evidence,
                status="completed",
                decision_outcome="approved",
                input_hash=input_hash,
                output_hash=output_hash,
                provider_name=selected_provider_name,
                provider_mode="stub",
            )
            await self.event_bus.publish(
                "workflow.completed",
                {"request_id": request_id, "status": "completed"},
            )

            gateway_provider_outcomes_total.labels(
                tenant_id=metadata.tenant_id,
                scenario=metadata.scenario or "unknown",
                provider_status="ok",
            ).inc()

            response_payload.update(
                {
                    "provider_used": selected_provider.__class__.__name__,
                    "status": "completed",
                    "result": enriched,
                    "supervisory_submission": supervisory_ack,
                }
            )
            return response_payload

        except Exception as exc:
            evidence = self.evidence_service.add_event(
                evidence,
                EvidenceEventType.PROVIDER_FAILED,
                {"error": str(exc)},
            )
            evidence = await self.evidence_service.finalize(
                evidence,
                status="fallback",
                decision_outcome="provider_failure",
                input_hash=input_hash,
                output_hash=None,
                provider_name=selected_provider_name,
                provider_mode="stub",
            )
            await self.event_bus.publish(
                "workflow.fallback",
                {
                    "request_id": request_id,
                    "tenant_id": metadata.tenant_id,
                    "error": str(exc),
                },
            )

            gateway_provider_outcomes_total.labels(
                tenant_id=metadata.tenant_id,
                scenario=metadata.scenario or "unknown",
                provider_status="fallback",
            ).inc()

            response_payload.update(
                {
                    "provider_used": selected_provider.__class__.__name__,
                    "status": "fallback",
                    "error": str(exc),
                }
            )
            return response_payload
