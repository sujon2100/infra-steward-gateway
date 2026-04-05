from __future__ import annotations

from typing import Any

from app.workflow.engine import WorkflowEngine

SCENARIO_ALPHA_COMPLIANT = "reporting"
SCENARIO_BETA_BLOCKED = "reporting"
SCENARIO_ALPHA_PROVIDER_FAILURE = "provider_failure"


class ScenarioRunner:
    def __init__(self, workflow_engine: WorkflowEngine) -> None:
        self.workflow_engine = workflow_engine

    async def run_bank_alpha_compliant(self) -> dict[str, Any]:
        request = {
            "tenant_id": "bank_alpha",
            "scenario": SCENARIO_ALPHA_COMPLIANT,
            "report_id": "alpha-compliant-1",
            "report_type": "standard",
            "payload": {"text": "demo compliant report"},
        }
        return await self.workflow_engine.process_report(request)

    async def run_bank_beta_blocked(self) -> dict[str, Any]:
        request = {
            "tenant_id": "bank_beta",
            "scenario": SCENARIO_BETA_BLOCKED,
            "report_id": "beta-blocked-1",
            "report_type": "standard",
            "payload": {"text": "demo blocked report"},
        }
        return await self.workflow_engine.process_report(request)

    async def run_bank_alpha_provider_failure(self) -> dict[str, Any]:
        request = {
            "tenant_id": "bank_alpha",
            "scenario": SCENARIO_ALPHA_PROVIDER_FAILURE,
            "report_id": "alpha-failure-1",
            "report_type": "standard",
            "payload": {"text": "demo provider failure", "provider_failure": True},
        }
        return await self.workflow_engine.process_report(request)
