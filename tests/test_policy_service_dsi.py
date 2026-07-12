"""
DSI transparency policy tests (HTI-1, 45 CFR 170.315(b)(11)). Same
grouping as tests/test_policy_service_phi.py: true negative (complete
registration, correctly allowed), true positive (one required attribute
missing, correctly blocked), edge, and adversarial. Each TP case isolates
exactly one of the eleven category 1-3 fields so a regression points at
the right one.
"""

from app.policy.dsi_models import DSIAdvisoryRequest, DSISourceAttributes
from app.policy.service import PolicyService


def _attrs(**overrides: object) -> DSISourceAttributes:
    defaults: dict[str, object] = {
        "dsi_id": "d1",
        "model_name": "TestSepsisScorer",
        "developer_name": "Acme Health",
        "developer_contact": "dev@acme.example",
        "funding_source": "internal R&D budget",
        "output_value_description": "48-hour sepsis risk score",
        "output_type": "prediction",
        "intended_use": "flag high-risk adult inpatients for clinician review",
        "intended_patient_population": "adult inpatients",
        "intended_users": ["physician"],
        "decision_making_role": "informs",
        "cautioned_out_of_scope_uses": ["pediatric patients"],
        "known_risks_and_limitations": "reduced sensitivity in patients with chronic renal disease",
    }
    defaults.update(overrides)
    return DSISourceAttributes(**defaults)  # type: ignore[arg-type]


def _request(**overrides: object) -> DSIAdvisoryRequest:
    defaults: dict[str, object] = {
        "dsi_id": "d1",
        "requesting_org": "hie_hospital_north",
        "encounter_id": "enc-1",
    }
    defaults.update(overrides)
    return DSIAdvisoryRequest(**defaults)  # type: ignore[arg-type]


def _service_with_dsi(**attr_overrides: object) -> PolicyService:
    service = PolicyService()
    service.register_dsi(_attrs(**attr_overrides))
    return service


# --- true negative: complete registration, correctly allowed ---


def test_tn_fully_registered_dsi_is_allowed() -> None:
    service = _service_with_dsi()
    decision = service.evaluate_dsi_output(_request())

    assert decision.allowed is True
    assert decision.missing_attributes == []
    assert decision.output_type is not None and decision.output_type.value == "prediction"


def test_tn_categories_four_and_seven_absent_still_allowed() -> None:
    # input_features, training data notes, and performance figures are all
    # unset here - none of that is enforced in this pass.
    service = _service_with_dsi()
    decision = service.evaluate_dsi_output(_request())

    assert decision.allowed is True


def test_tn_funding_source_disclosed_as_none_still_counts_as_present() -> None:
    service = _service_with_dsi(funding_source="none, self-funded")
    decision = service.evaluate_dsi_output(_request())

    assert decision.allowed is True


def test_tn_single_entry_lists_are_sufficient() -> None:
    service = _service_with_dsi(
        intended_users=["nurse practitioner"],
        cautioned_out_of_scope_uses=["outpatient settings"],
    )
    decision = service.evaluate_dsi_output(_request())

    assert decision.allowed is True


# --- true positive: exactly one required attribute missing ---


def test_tp_unknown_dsi_id() -> None:
    service = PolicyService()
    decision = service.evaluate_dsi_output(_request(dsi_id="does-not-exist"))

    assert decision.allowed is False
    assert "No DSI registration found" in decision.reason


def test_tp_missing_developer_name() -> None:
    service = _service_with_dsi(developer_name=None)
    decision = service.evaluate_dsi_output(_request())

    assert decision.allowed is False
    assert decision.missing_attributes == ["developer_name"]


def test_tp_missing_developer_contact() -> None:
    service = _service_with_dsi(developer_contact=None)
    decision = service.evaluate_dsi_output(_request())

    assert decision.missing_attributes == ["developer_contact"]


def test_tp_missing_funding_source() -> None:
    service = _service_with_dsi(funding_source=None)
    decision = service.evaluate_dsi_output(_request())

    assert decision.missing_attributes == ["funding_source"]


def test_tp_missing_output_value_description() -> None:
    service = _service_with_dsi(output_value_description=None)
    decision = service.evaluate_dsi_output(_request())

    assert decision.missing_attributes == ["output_value_description"]


def test_tp_missing_output_type() -> None:
    service = _service_with_dsi(output_type=None)
    decision = service.evaluate_dsi_output(_request())

    assert decision.missing_attributes == ["output_type"]


def test_tp_missing_intended_use() -> None:
    service = _service_with_dsi(intended_use=None)
    decision = service.evaluate_dsi_output(_request())

    assert decision.missing_attributes == ["intended_use"]


def test_tp_missing_intended_patient_population() -> None:
    service = _service_with_dsi(intended_patient_population=None)
    decision = service.evaluate_dsi_output(_request())

    assert decision.missing_attributes == ["intended_patient_population"]


def test_tp_missing_intended_users() -> None:
    service = _service_with_dsi(intended_users=[])
    decision = service.evaluate_dsi_output(_request())

    assert decision.missing_attributes == ["intended_users"]


def test_tp_missing_decision_making_role() -> None:
    service = _service_with_dsi(decision_making_role=None)
    decision = service.evaluate_dsi_output(_request())

    assert decision.missing_attributes == ["decision_making_role"]


def test_tp_missing_cautioned_out_of_scope_uses() -> None:
    service = _service_with_dsi(cautioned_out_of_scope_uses=[])
    decision = service.evaluate_dsi_output(_request())

    assert decision.missing_attributes == ["cautioned_out_of_scope_uses"]


def test_tp_missing_known_risks_and_limitations() -> None:
    service = _service_with_dsi(known_risks_and_limitations=None)
    decision = service.evaluate_dsi_output(_request())

    assert decision.missing_attributes == ["known_risks_and_limitations"]


# --- edge cases ---


def test_edge_whitespace_only_field_treated_as_missing() -> None:
    service = _service_with_dsi(developer_name="   ")
    decision = service.evaluate_dsi_output(_request())

    assert decision.allowed is False
    assert decision.missing_attributes == ["developer_name"]


def test_edge_list_with_only_blank_entries_treated_as_missing() -> None:
    service = _service_with_dsi(intended_users=["  ", ""])
    decision = service.evaluate_dsi_output(_request())

    assert decision.allowed is False
    assert decision.missing_attributes == ["intended_users"]


def test_edge_list_with_one_real_entry_among_blanks_is_present() -> None:
    service = _service_with_dsi(intended_users=["  ", "physician", ""])
    decision = service.evaluate_dsi_output(_request())

    assert decision.allowed is True


# --- adversarial ---


def test_adversarial_multiple_missing_fields_are_all_reported_not_just_first() -> None:
    service = _service_with_dsi(
        developer_name=None,
        output_type=None,
        cautioned_out_of_scope_uses=[],
    )
    decision = service.evaluate_dsi_output(_request())

    assert decision.allowed is False
    assert set(decision.missing_attributes) == {
        "developer_name",
        "output_type",
        "cautioned_out_of_scope_uses",
    }


def test_adversarial_reregistering_same_dsi_id_with_incomplete_attributes() -> None:
    # There's no versioning or immutability on registration - a later
    # incomplete registration silently overwrites an earlier complete one.
    # This documents that as current behavior, not as a guarantee.
    service = _service_with_dsi()
    allowed_before = service.evaluate_dsi_output(_request()).allowed
    assert allowed_before is True

    service.register_dsi(_attrs(developer_name=None))
    decision_after = service.evaluate_dsi_output(_request())

    assert decision_after.allowed is False
    assert decision_after.missing_attributes == ["developer_name"]
