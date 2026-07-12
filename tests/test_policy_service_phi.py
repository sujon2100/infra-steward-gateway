"""
Consent-scope and purpose-of-use policy tests for the HIE PHI exchange
scenario. Grouped the same way the accuracy evaluation in
tests/evaluation/test_phi_policy_accuracy.py labels cases: true negative
(compliant, correctly allowed), true positive (violation, correctly
denied), edge, and adversarial. Each denial test targets exactly one rule
so a regression points at the right line in PolicyService.
"""

from datetime import UTC, datetime, timedelta

from app.policy.models import ConsentRecord, PHIExchangeRequest
from app.policy.service import PolicyService


def _consent(**overrides: object) -> ConsentRecord:
    defaults: dict[str, object] = {
        "consent_id": "c1",
        "patient_id": "p1",
        "granted_categories": {"diagnosis", "medication"},
        "granted_purposes": {"treatment", "healthcare_operations"},
        "authorized_recipients": {"hie_hospital_north"},
    }
    defaults.update(overrides)
    return ConsentRecord(**defaults)  # type: ignore[arg-type]


def _request(**overrides: object) -> PHIExchangeRequest:
    defaults: dict[str, object] = {
        "consent_id": "c1",
        "patient_id": "p1",
        "disclosing_org": "hie_clinic_riverside",
        "receiving_org": "hie_hospital_north",
        "categories": {"diagnosis"},
        "purpose_of_use": "treatment",
    }
    defaults.update(overrides)
    return PHIExchangeRequest(**defaults)  # type: ignore[arg-type]


def _service_with_consent(**consent_overrides: object) -> PolicyService:
    service = PolicyService()
    service.register_consent(_consent(**consent_overrides))
    return service


# --- true negative: compliant requests correctly allowed ---


def test_tn_treatment_request_within_consent_scope() -> None:
    service = _service_with_consent()
    decision = service.evaluate_phi_exchange(_request())

    assert decision.allowed is True
    assert decision.disclosing_org == "hie_clinic_riverside"
    assert decision.policies_applied[-1] == "restricted_category_policy"


def test_tn_patient_request_purpose_for_restricted_category() -> None:
    service = _service_with_consent(
        granted_categories={"mental_health"},
        granted_purposes={"patient_request"},
    )
    decision = service.evaluate_phi_exchange(
        _request(categories={"mental_health"}, purpose_of_use="patient_request")
    )

    assert decision.allowed is True


def test_tn_wildcard_recipient_allows_any_registered_org() -> None:
    service = _service_with_consent(authorized_recipients={"*"})
    decision = service.evaluate_phi_exchange(
        _request(receiving_org="hie_clinic_riverside", categories={"diagnosis"})
    )

    assert decision.allowed is True


def test_tn_payer_payment_purpose() -> None:
    service = _service_with_consent(
        granted_categories={"demographic"},
        granted_purposes={"payment"},
        authorized_recipients={"hie_payer_horizon"},
    )
    decision = service.evaluate_phi_exchange(
        _request(
            receiving_org="hie_payer_horizon",
            categories={"demographic"},
            purpose_of_use="payment",
        )
    )

    assert decision.allowed is True


def test_tn_research_org_research_purpose() -> None:
    service = _service_with_consent(
        granted_categories={"lab_result"},
        granted_purposes={"research"},
        authorized_recipients={"hie_research_lab"},
    )
    decision = service.evaluate_phi_exchange(
        _request(
            receiving_org="hie_research_lab",
            categories={"lab_result"},
            purpose_of_use="research",
        )
    )

    assert decision.allowed is True


# --- true positive: violations correctly denied, one rule per case ---


def test_tp_unknown_consent_id() -> None:
    service = PolicyService()
    decision = service.evaluate_phi_exchange(_request(consent_id="does-not-exist"))

    assert decision.allowed is False
    assert "No consent record found" in decision.reason


def test_tp_consent_does_not_belong_to_patient() -> None:
    service = _service_with_consent(patient_id="p1")
    decision = service.evaluate_phi_exchange(_request(patient_id="p2"))

    assert decision.allowed is False
    assert "does not belong to patient" in decision.reason


def test_tp_revoked_consent() -> None:
    service = _service_with_consent(revoked=True)
    decision = service.evaluate_phi_exchange(_request())

    assert decision.allowed is False
    assert "revoked" in decision.reason


def test_tp_expired_consent() -> None:
    service = _service_with_consent(expires_at=datetime.now(UTC) - timedelta(days=1))
    decision = service.evaluate_phi_exchange(_request())

    assert decision.allowed is False
    assert "expired" in decision.reason


def test_tp_receiving_org_not_a_hie_participant() -> None:
    service = _service_with_consent(authorized_recipients={"*"})
    decision = service.evaluate_phi_exchange(_request(receiving_org="not_a_real_org"))

    assert decision.allowed is False
    assert "not a registered HIE participant" in decision.reason


def test_tp_org_type_not_authorized_for_purpose() -> None:
    service = _service_with_consent(
        granted_purposes={"treatment", "payment"},
        authorized_recipients={"hie_payer_horizon"},
    )
    decision = service.evaluate_phi_exchange(
        _request(receiving_org="hie_payer_horizon", purpose_of_use="treatment")
    )

    assert decision.allowed is False
    assert "not authorized for purpose" in decision.reason


def test_tp_consent_does_not_grant_purpose() -> None:
    service = _service_with_consent(granted_purposes={"healthcare_operations"})
    decision = service.evaluate_phi_exchange(_request(purpose_of_use="treatment"))

    assert decision.allowed is False
    assert "does not authorize purpose" in decision.reason


def test_tp_consent_does_not_authorize_recipient() -> None:
    service = _service_with_consent(authorized_recipients={"hie_clinic_riverside"})
    decision = service.evaluate_phi_exchange(_request(receiving_org="hie_hospital_north"))

    assert decision.allowed is False
    assert "does not authorize disclosure" in decision.reason


def test_tp_consent_does_not_cover_category() -> None:
    service = _service_with_consent(granted_categories={"demographic"})
    decision = service.evaluate_phi_exchange(_request(categories={"medication"}))

    assert decision.allowed is False
    assert "does not cover categories" in decision.reason


def test_tp_restricted_category_wrong_purpose() -> None:
    service = _service_with_consent(
        granted_categories={"substance_use"},
        granted_purposes={"healthcare_operations"},
    )
    decision = service.evaluate_phi_exchange(
        _request(categories={"substance_use"}, purpose_of_use="healthcare_operations")
    )

    assert decision.allowed is False
    assert "require a treatment or patient_request purpose" in decision.reason


# --- edge cases ---


def test_edge_consent_with_no_expiry_never_expires() -> None:
    service = _service_with_consent(expires_at=None)
    decision = service.evaluate_phi_exchange(_request())

    assert decision.allowed is True


def test_edge_mixed_restricted_and_ordinary_category_with_valid_purpose() -> None:
    service = _service_with_consent(
        granted_categories={"substance_use", "diagnosis"},
        granted_purposes={"treatment"},
    )
    decision = service.evaluate_phi_exchange(
        _request(categories={"substance_use", "diagnosis"}, purpose_of_use="treatment")
    )

    assert decision.allowed is True


def test_edge_requested_categories_exactly_match_grant() -> None:
    service = _service_with_consent(granted_categories={"diagnosis", "medication"})
    decision = service.evaluate_phi_exchange(_request(categories={"diagnosis", "medication"}))

    assert decision.allowed is True
    assert decision.phi_categories == ["diagnosis", "medication"]


# --- adversarial: attempts to slip a disallowed disclosure past a subset of the rules ---


def test_adversarial_borrowed_consent_id_for_different_patient() -> None:
    service = _service_with_consent(patient_id="patient-real")
    decision = service.evaluate_phi_exchange(
        _request(patient_id="patient-attacker-supplied")
    )

    assert decision.allowed is False
    assert decision.policies_applied[-1] == "consent_identity_check"


def test_adversarial_mixing_restricted_category_into_otherwise_valid_request() -> None:
    # Consent and org-type checks would all pass for healthcare_operations;
    # smuggling substance_use into the category set must still get caught
    # by the restricted-category rule, independent of everything else.
    service = _service_with_consent(
        granted_categories={"diagnosis", "substance_use"},
        granted_purposes={"healthcare_operations"},
    )
    decision = service.evaluate_phi_exchange(
        _request(categories={"diagnosis", "substance_use"}, purpose_of_use="healthcare_operations")
    )

    assert decision.allowed is False
    assert decision.policies_applied[-1] == "restricted_category_policy"


def test_adversarial_stale_consent_reused_after_expiry() -> None:
    service = _service_with_consent(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    decision = service.evaluate_phi_exchange(_request())

    assert decision.allowed is False
    assert decision.policies_applied[-1] == "consent_status_check"


def test_adversarial_recipient_not_in_narrowed_consent_list() -> None:
    # Org type and purpose would both clear for hie_hospital_north; the
    # consent just never named it as an authorized recipient.
    service = _service_with_consent(authorized_recipients={"hie_payer_horizon"})
    decision = service.evaluate_phi_exchange(
        _request(receiving_org="hie_hospital_north", categories={"diagnosis"})
    )

    assert decision.allowed is False
    assert decision.policies_applied[-1] == "consent_recipient_policy"
