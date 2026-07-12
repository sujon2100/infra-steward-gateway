"""
Labeled case set for the PHI consent/purpose-of-use policy evaluation.

Each case is hand-labeled against the rule order documented in
PolicyService.evaluate_phi_exchange (app/policy/service.py). This is a
specification-conformance check, not independent third-party validation:
the same person wrote the rules and the expected labels below. What it
does verify is that the implementation matches the written spec across a
deliberately constructed set of compliant, violating, boundary, and
adversarial inputs — not that the spec itself is a correct reading of
HIPAA (it isn't reviewed by counsel; see design note).

Positive class for the confusion matrix is "should be denied" (a
violation). TN cases are compliant requests that must be allowed; TP
cases are violations that must be denied, each isolating one rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.policy.models import ConsentRecord, PHIExchangeRequest


@dataclass(frozen=True)
class PHIPolicyCase:
    name: str
    group: str  # "TN", "TP", "edge", "adversarial"
    consent: ConsentRecord | None
    request: PHIExchangeRequest
    expected_allowed: bool
    note: str


def _c(consent_id: str = "c1", patient_id: str = "p1", **kw: object) -> ConsentRecord:
    defaults: dict[str, object] = {
        "consent_id": consent_id,
        "patient_id": patient_id,
        "granted_categories": {"diagnosis"},
        "granted_purposes": {"treatment"},
        "authorized_recipients": {"*"},
    }
    defaults.update(kw)
    return ConsentRecord(**defaults)  # type: ignore[arg-type]


def _r(consent_id: str = "c1", patient_id: str = "p1", **kw: object) -> PHIExchangeRequest:
    defaults: dict[str, object] = {
        "consent_id": consent_id,
        "patient_id": patient_id,
        "disclosing_org": "hie_clinic_riverside",
        "receiving_org": "hie_hospital_north",
        "categories": {"diagnosis"},
        "purpose_of_use": "treatment",
    }
    defaults.update(kw)
    return PHIExchangeRequest(**defaults)  # type: ignore[arg-type]


def build_dataset() -> list[PHIPolicyCase]:
    cases: list[PHIPolicyCase] = []

    # --- true negatives: compliant baselines across org types and purposes ---

    cases.append(
        PHIPolicyCase(
            "tn_hospital_treatment",
            "TN",
            _c(granted_categories={"diagnosis"}, granted_purposes={"treatment"}),
            _r(receiving_org="hie_hospital_north", categories={"diagnosis"}, purpose_of_use="treatment"),
            True,
            "hospital, treatment, ordinary category, fully covered by consent",
        )
    )
    cases.append(
        PHIPolicyCase(
            "tn_clinic_treatment",
            "TN",
            _c(granted_categories={"medication"}, granted_purposes={"treatment"}),
            _r(receiving_org="hie_clinic_riverside", categories={"medication"}, purpose_of_use="treatment"),
            True,
            "clinic, treatment, ordinary category",
        )
    )
    cases.append(
        PHIPolicyCase(
            "tn_payer_payment",
            "TN",
            _c(granted_categories={"demographic"}, granted_purposes={"payment"}),
            _r(receiving_org="hie_payer_horizon", categories={"demographic"}, purpose_of_use="payment"),
            True,
            "payer is only ever allowed payment/healthcare_operations, this is in-scope",
        )
    )
    cases.append(
        PHIPolicyCase(
            "tn_hospital_public_health",
            "TN",
            _c(granted_categories={"lab_result"}, granted_purposes={"public_health"}),
            _r(receiving_org="hie_hospital_north", categories={"lab_result"}, purpose_of_use="public_health"),
            True,
            "public_health is on the hospital allow-list and consent grants it",
        )
    )
    cases.append(
        PHIPolicyCase(
            "tn_research_org_research",
            "TN",
            _c(granted_categories={"genetic"}, granted_purposes={"research"}, authorized_recipients={"hie_research_lab"}),
            _r(receiving_org="hie_research_lab", categories={"genetic"}, purpose_of_use="research"),
            True,
            "research org restricted to research purpose only, this matches",
        )
    )
    cases.append(
        PHIPolicyCase(
            "tn_hospital_patient_request_mental_health",
            "TN",
            _c(granted_categories={"mental_health"}, granted_purposes={"patient_request"}),
            _r(receiving_org="hie_hospital_north", categories={"mental_health"}, purpose_of_use="patient_request"),
            True,
            "restricted category, but purpose satisfies the extra restricted-category rule",
        )
    )
    cases.append(
        PHIPolicyCase(
            "tn_clinic_patient_request_substance_use",
            "TN",
            _c(granted_categories={"substance_use"}, granted_purposes={"patient_request"}),
            _r(receiving_org="hie_clinic_riverside", categories={"substance_use"}, purpose_of_use="patient_request"),
            True,
            "same as above via a clinic instead of a hospital",
        )
    )
    cases.append(
        PHIPolicyCase(
            "tn_hospital_healthcare_operations",
            "TN",
            _c(granted_categories={"diagnosis"}, granted_purposes={"healthcare_operations"}),
            _r(receiving_org="hie_hospital_north", categories={"diagnosis"}, purpose_of_use="healthcare_operations"),
            True,
            "ordinary category under healthcare_operations, no restricted-category rule involved",
        )
    )

    # --- true positives: one rule violated per case, three donor baselines ---

    donors = [
        ("hospital", "hie_hospital_north", "treatment", {"diagnosis"}, {"treatment", "healthcare_operations"}),
        ("payer", "hie_payer_horizon", "payment", {"demographic"}, {"payment", "healthcare_operations"}),
        (
            "hospital_patient_request",
            "hie_hospital_north",
            "patient_request",
            {"mental_health"},
            {"patient_request"},
        ),
    ]

    for label, org, purpose, cats, consent_purposes in donors:
        consent = _c(granted_categories=cats, granted_purposes=consent_purposes)
        base_request = _r(receiving_org=org, categories=cats, purpose_of_use=purpose)

        cases.append(
            PHIPolicyCase(
                f"tp_{label}_unknown_consent",
                "TP",
                None,
                _r(consent_id="ghost", receiving_org=org, categories=cats, purpose_of_use=purpose),
                False,
                "consent_id does not exist",
            )
        )
        cases.append(
            PHIPolicyCase(
                f"tp_{label}_patient_mismatch",
                "TP",
                consent,
                _r(patient_id="someone-else", receiving_org=org, categories=cats, purpose_of_use=purpose),
                False,
                "consent belongs to a different patient than the request claims",
            )
        )
        cases.append(
            PHIPolicyCase(
                f"tp_{label}_revoked",
                "TP",
                _c(granted_categories=cats, granted_purposes=consent_purposes, revoked=True),
                base_request,
                False,
                "consent has been revoked",
            )
        )
        cases.append(
            PHIPolicyCase(
                f"tp_{label}_expired",
                "TP",
                _c(
                    granted_categories=cats,
                    granted_purposes=consent_purposes,
                    expires_at=datetime.now(UTC) - timedelta(days=30),
                ),
                base_request,
                False,
                "consent expired a month ago",
            )
        )
        cases.append(
            PHIPolicyCase(
                f"tp_{label}_unregistered_org",
                "TP",
                consent,
                _r(receiving_org="not_a_real_org", categories=cats, purpose_of_use=purpose),
                False,
                "receiving org is not in the HIE participant directory",
            )
        )
        cases.append(
            PHIPolicyCase(
                f"tp_{label}_recipient_not_authorized",
                "TP",
                _c(granted_categories=cats, granted_purposes=consent_purposes, authorized_recipients={"someone_else"}),
                base_request,
                False,
                "consent names a different recipient",
            )
        )
        cases.append(
            PHIPolicyCase(
                f"tp_{label}_category_not_covered",
                "TP",
                _c(granted_categories={"genetic"}, granted_purposes=consent_purposes),
                base_request,
                False,
                "consent covers a category the request doesn't even ask for",
            )
        )

    # org-purpose mismatch: needs a purpose the org type disallows even though consent grants it
    cases.append(
        PHIPolicyCase(
            "tp_payer_requesting_treatment",
            "TP",
            _c(granted_categories={"diagnosis"}, granted_purposes={"treatment"}, authorized_recipients={"hie_payer_horizon"}),
            _r(receiving_org="hie_payer_horizon", categories={"diagnosis"}, purpose_of_use="treatment"),
            False,
            "payers are never authorized for treatment purpose, regardless of consent",
        )
    )
    cases.append(
        PHIPolicyCase(
            "tp_research_org_requesting_treatment",
            "TP",
            _c(granted_categories={"diagnosis"}, granted_purposes={"treatment"}, authorized_recipients={"hie_research_lab"}),
            _r(receiving_org="hie_research_lab", categories={"diagnosis"}, purpose_of_use="treatment"),
            False,
            "research orgs are only ever authorized for research purpose",
        )
    )

    # consent doesn't grant the purpose, even though org type would allow it
    cases.append(
        PHIPolicyCase(
            "tp_hospital_consent_missing_purpose",
            "TP",
            _c(granted_categories={"diagnosis"}, granted_purposes={"healthcare_operations"}),
            _r(receiving_org="hie_hospital_north", categories={"diagnosis"}, purpose_of_use="treatment"),
            False,
            "consent grants healthcare_operations only, request asks for treatment",
        )
    )

    # restricted-category rule specifically, isolated from the org/purpose checks
    cases.append(
        PHIPolicyCase(
            "tp_restricted_category_healthcare_operations",
            "TP",
            _c(granted_categories={"substance_use"}, granted_purposes={"healthcare_operations"}),
            _r(receiving_org="hie_hospital_north", categories={"substance_use"}, purpose_of_use="healthcare_operations"),
            False,
            "substance_use requires treatment/patient_request even under an otherwise valid grant",
        )
    )
    cases.append(
        PHIPolicyCase(
            "tp_restricted_category_public_health",
            "TP",
            _c(granted_categories={"mental_health"}, granted_purposes={"public_health"}),
            _r(receiving_org="hie_hospital_north", categories={"mental_health"}, purpose_of_use="public_health"),
            False,
            "mental_health cannot be shared for public_health purpose under this policy",
        )
    )

    # --- edge cases ---

    cases.append(
        PHIPolicyCase(
            "edge_no_expiry_set",
            "edge",
            _c(granted_categories={"diagnosis"}, granted_purposes={"treatment"}, expires_at=None),
            _r(receiving_org="hie_hospital_north", categories={"diagnosis"}, purpose_of_use="treatment"),
            True,
            "no expiry means the consent doesn't lapse on its own",
        )
    )
    cases.append(
        PHIPolicyCase(
            "edge_expires_one_second_from_now",
            "edge",
            _c(
                granted_categories={"diagnosis"},
                granted_purposes={"treatment"},
                expires_at=datetime.now(UTC) + timedelta(seconds=1),
            ),
            _r(receiving_org="hie_hospital_north", categories={"diagnosis"}, purpose_of_use="treatment"),
            True,
            "still valid at evaluation time, just barely",
        )
    )
    cases.append(
        PHIPolicyCase(
            "edge_expired_one_second_ago",
            "edge",
            _c(
                granted_categories={"diagnosis"},
                granted_purposes={"treatment"},
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            ),
            _r(receiving_org="hie_hospital_north", categories={"diagnosis"}, purpose_of_use="treatment"),
            False,
            "just past expiry, boundary on the other side",
        )
    )
    cases.append(
        PHIPolicyCase(
            "edge_multiple_categories_exact_match",
            "edge",
            _c(granted_categories={"diagnosis", "medication", "lab_result"}, granted_purposes={"treatment"}),
            _r(
                receiving_org="hie_hospital_north",
                categories={"diagnosis", "medication", "lab_result"},
                purpose_of_use="treatment",
            ),
            True,
            "requested set exactly equals granted set",
        )
    )
    cases.append(
        PHIPolicyCase(
            "edge_requesting_subset_of_grant",
            "edge",
            _c(granted_categories={"diagnosis", "medication", "lab_result"}, granted_purposes={"treatment"}),
            _r(receiving_org="hie_hospital_north", categories={"diagnosis"}, purpose_of_use="treatment"),
            True,
            "asking for less than the consent grants is fine",
        )
    )
    cases.append(
        PHIPolicyCase(
            "edge_restricted_plus_ordinary_category_valid_purpose",
            "edge",
            _c(granted_categories={"substance_use", "diagnosis"}, granted_purposes={"treatment"}),
            _r(receiving_org="hie_hospital_north", categories={"substance_use", "diagnosis"}, purpose_of_use="treatment"),
            True,
            "mixing a restricted and ordinary category is fine when the purpose qualifies",
        )
    )
    cases.append(
        PHIPolicyCase(
            "edge_wildcard_recipient_with_unusual_but_registered_org",
            "edge",
            _c(granted_categories={"lab_result"}, granted_purposes={"research"}, authorized_recipients={"*"}),
            _r(receiving_org="hie_research_lab", categories={"lab_result"}, purpose_of_use="research"),
            True,
            "wildcard recipient still has to clear the org-type/purpose check",
        )
    )

    # --- adversarial: crafted to look compliant on most dimensions ---

    cases.append(
        PHIPolicyCase(
            "adversarial_borrowed_consent_otherwise_perfect",
            "adversarial",
            _c(patient_id="real-patient", granted_categories={"diagnosis"}, granted_purposes={"treatment"}),
            _r(patient_id="attacker-supplied-id", receiving_org="hie_hospital_north", categories={"diagnosis"}, purpose_of_use="treatment"),
            False,
            "every other field matches a legitimate exchange; only the patient binding is wrong",
        )
    )
    cases.append(
        PHIPolicyCase(
            "adversarial_smuggled_restricted_category",
            "adversarial",
            _c(granted_categories={"diagnosis", "substance_use"}, granted_purposes={"healthcare_operations"}),
            _r(receiving_org="hie_hospital_north", categories={"diagnosis", "substance_use"}, purpose_of_use="healthcare_operations"),
            False,
            "consent nominally covers both categories and the purpose; restricted-category rule must still fire",
        )
    )
    cases.append(
        PHIPolicyCase(
            "adversarial_stale_consent_still_named_as_recipient",
            "adversarial",
            _c(
                granted_categories={"diagnosis"},
                granted_purposes={"treatment"},
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            ),
            _r(receiving_org="hie_hospital_north", categories={"diagnosis"}, purpose_of_use="treatment"),
            False,
            "recipient and scope are correct, consent is simply expired",
        )
    )
    cases.append(
        PHIPolicyCase(
            "adversarial_payer_masquerading_as_operations_request",
            "adversarial",
            _c(granted_categories={"diagnosis"}, granted_purposes={"treatment", "healthcare_operations"}, authorized_recipients={"hie_payer_horizon"}),
            _r(receiving_org="hie_payer_horizon", categories={"diagnosis"}, purpose_of_use="healthcare_operations"),
            True,
            "healthcare_operations is legitimately on the payer allow-list, this one should pass",
        )
    )
    cases.append(
        PHIPolicyCase(
            "adversarial_narrow_recipient_list_correctly_excludes_third_party",
            "adversarial",
            _c(granted_categories={"diagnosis"}, granted_purposes={"treatment"}, authorized_recipients={"hie_clinic_riverside"}),
            _r(receiving_org="hie_hospital_north", categories={"diagnosis"}, purpose_of_use="treatment"),
            False,
            "consent names a specific clinic, hospital was never authorized",
        )
    )
    cases.append(
        PHIPolicyCase(
            "adversarial_request_fewer_categories_than_consent_looks_suspicious_but_is_fine",
            "adversarial",
            _c(granted_categories={"diagnosis", "mental_health"}, granted_purposes={"treatment"}),
            _r(receiving_org="hie_hospital_north", categories={"diagnosis"}, purpose_of_use="treatment"),
            True,
            "requesting only the ordinary category out of a broader grant is not a violation",
        )
    )
    cases.append(
        PHIPolicyCase(
            "adversarial_two_faults_at_once",
            "adversarial",
            _c(granted_categories={"diagnosis"}, granted_purposes={"payment"}, revoked=True),
            _r(receiving_org="hie_hospital_north", categories={"diagnosis"}, purpose_of_use="treatment"),
            False,
            "revoked and purpose-mismatched at the same time, the check must still deny once",
        )
    )

    return cases
