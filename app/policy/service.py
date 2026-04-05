"""
PolicyService implementation for Phase 2.
"""

from __future__ import annotations

from datetime import datetime

from app.policy.models import PolicyDecision


class PolicyService:
    DEFAULT_PROVIDER_NAME = "stub_a"

    _TENANT_PROVIDER_MAP: dict[str, str] = {
        "bank_alpha": "stub_a",
        "bank_beta": "stub_b",
        "bank_mars": "stub_a",
        "bank_neptune": "stub_b",
    }

    # Jurisdictions a tenant is permitted to submit from. A request whose
    # resolved tenant context carries a jurisdiction outside this set is
    # denied by policy regardless of scenario.
    _TENANT_ALLOWED_JURISDICTIONS: dict[str, set[str]] = {
        "bank_alpha": {"EU"},
        "bank_beta": {"EU"},
        "bank_mars": {"US"},
        "bank_neptune": {"APAC"},
    }

    def __init__(self, policy_suite_version: str = "v1"):
        self.policy_suite_version = policy_suite_version
        self._policies = self._load_policies()

    def _provider_for_tenant(self, tenant_id_lower: str) -> str:
        return self._TENANT_PROVIDER_MAP.get(tenant_id_lower, self.DEFAULT_PROVIDER_NAME)

    def _jurisdiction_allowed(self, tenant_id_lower: str, jurisdiction: str | None) -> bool:
        if jurisdiction is None:
            return True
        allowed = self._TENANT_ALLOWED_JURISDICTIONS.get(tenant_id_lower)
        if allowed is None:
            return True
        return jurisdiction in allowed

    def _load_policies(self) -> dict[str, dict[str, list[str]]]:
        # Simplified policy-as-code bundle for Phase 2.
        # Each tenant has disallowed scenarios or report_type values.
        return {
            "bank_alpha": {
                "allowed_scenarios": ["*"]
            },
            "bank_beta": {
                "allowed_scenarios": ["analysis"],
                "blocked_report_types": ["sensitive", "confidential"]
            },
        }

    def evaluate(
        self,
        tenant_id: str,
        scenario: str | None = None,
        report_type: str | None = None,
        jurisdiction: str | None = None,
    ) -> PolicyDecision:
        tenant_id_lower = tenant_id.lower().strip()
        policies_applied: list[str] = []
        allowed = True
        reason = "Tenant policy default allow"

        if tenant_id_lower == "bank_alpha":
            policies_applied.append("bank_alpha_policy")
            allowed = True
            reason = "Bank Alpha allows all scenarios"

        elif tenant_id_lower == "bank_beta":
            policies_applied.append("bank_beta_policy")
            # bank_beta: allow analysis only
            if scenario is not None and scenario != "analysis":
                allowed = False
                reason = f"Bank Beta does not allow scenario '{scenario}'"

            if report_type is not None and report_type in ["sensitive", "confidential"]:
                allowed = False
                reason = f"Bank Beta blocks report type '{report_type}'"

            if allowed:
                reason = "Bank Beta allows requested scenario/report type"

        elif tenant_id_lower == "bank_mars":
            policies_applied.append("bank_mars_policy")
            allowed = True
            reason = "Bank Mars allows all scenarios"

        elif tenant_id_lower == "bank_neptune":
            policies_applied.append("bank_neptune_policy")
            allowed = True
            reason = "Bank Neptune allows all scenarios"

        else:
            policies_applied.append("default_policy")
            allowed = False
            reason = f"No policy defined for tenant '{tenant_id}'"

        # Jurisdiction check runs last and can override any allow above.
        if allowed and not self._jurisdiction_allowed(tenant_id_lower, jurisdiction):
            allowed = False
            reason = (
                f"Tenant '{tenant_id}' is not permitted to submit from "
                f"jurisdiction '{jurisdiction}'"
            )
            policies_applied.append("jurisdiction_policy")

        selected_provider = self._provider_for_tenant(tenant_id_lower) if allowed else None

        return PolicyDecision(
            allowed=allowed,
            reason=reason,
            tenant_id=tenant_id,
            policies_applied=policies_applied,
            policy_suite_version=self.policy_suite_version,
            selected_provider=selected_provider,
            timestamp=datetime.utcnow(),
        )
