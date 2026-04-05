"""
Tests for PolicyService.
"""

from app.policy.service import PolicyService


def test_policy_service_bank_alpha_allowed() -> None:
    service = PolicyService()
    decision = service.evaluate(tenant_id="bank_alpha", scenario="reporting", report_type="standard")

    assert decision.allowed is True
    assert decision.policies_applied == ["bank_alpha_policy"]
    assert decision.policy_suite_version == "v1"
    assert "Bank Alpha" in decision.reason


def test_policy_service_bank_beta_blocked_scenario() -> None:
    service = PolicyService()
    decision = service.evaluate(tenant_id="bank_beta", scenario="reporting", report_type="standard")

    assert decision.allowed is False
    assert decision.policies_applied == ["bank_beta_policy"]
    assert decision.policy_suite_version == "v1"
    assert "does not allow scenario" in decision.reason


def test_policy_service_bank_beta_blocked_report_type() -> None:
    service = PolicyService()
    decision = service.evaluate(tenant_id="bank_beta", scenario="analysis", report_type="sensitive")

    assert decision.allowed is False
    assert decision.policies_applied == ["bank_beta_policy"]
    assert decision.policy_suite_version == "v1"
    assert "blocks report type" in decision.reason
