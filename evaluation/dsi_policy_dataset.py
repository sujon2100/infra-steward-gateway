"""
Labeled case set for the DSI transparency policy evaluation (HTI-1,
45 CFR 170.315(b)(11)). Same caveat as evaluation/phi_policy_dataset.py:
labels are hand-derived from the same spec the implementation follows, by
the same author. This checks spec conformance, not independent
validation - and it says nothing about whether the underlying model
behind a given dsi_id is actually accurate, fair, or safe. That's a
different problem this branch doesn't touch.

Positive class is "should be blocked" (a required attribute missing, or
the DSI isn't registered at all).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.policy.dsi_models import DSIAdvisoryRequest, DSISourceAttributes


@dataclass(frozen=True)
class DSIPolicyCase:
    name: str
    group: str  # "TN", "TP", "edge", "adversarial"
    attrs: DSISourceAttributes | None
    request: DSIAdvisoryRequest
    expected_allowed: bool
    note: str


def _a(dsi_id: str = "d1", **kw: object) -> DSISourceAttributes:
    defaults: dict[str, object] = {
        "dsi_id": dsi_id,
        "model_name": "EvalScorer",
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
        "known_risks_and_limitations": "reduced sensitivity in chronic renal disease",
    }
    defaults.update(kw)
    return DSISourceAttributes(**defaults)  # type: ignore[arg-type]


def _r(dsi_id: str = "d1", **kw: object) -> DSIAdvisoryRequest:
    defaults: dict[str, object] = {
        "dsi_id": dsi_id,
        "requesting_org": "hie_hospital_north",
        "encounter_id": "enc-1",
    }
    defaults.update(kw)
    return DSIAdvisoryRequest(**defaults)  # type: ignore[arg-type]


_REQUIRED_FIELDS_TEXT = [
    "developer_name",
    "developer_contact",
    "funding_source",
    "output_value_description",
    "intended_use",
    "intended_patient_population",
    "known_risks_and_limitations",
]
_REQUIRED_FIELDS_ENUM = ["output_type", "decision_making_role"]
_REQUIRED_FIELDS_LIST = ["intended_users", "cautioned_out_of_scope_uses"]


def build_dataset() -> list[DSIPolicyCase]:
    cases: list[DSIPolicyCase] = []

    # --- true negatives ---

    cases.append(
        DSIPolicyCase(
            "tn_fully_registered",
            "TN",
            _a(),
            _r(),
            True,
            "all category 1-3 fields present",
        )
    )
    cases.append(
        DSIPolicyCase(
            "tn_categories_four_seven_absent",
            "TN",
            _a(),  # category 4/7 fields are already unset by default
            _r(),
            True,
            "categories 4 and 7 aren't enforced in this pass",
        )
    )
    cases.append(
        DSIPolicyCase(
            "tn_funding_source_disclosed_as_none",
            "TN",
            _a(funding_source="none, self-funded"),
            _r(),
            True,
            "a disclosed absence of funding still counts as disclosure",
        )
    )
    cases.append(
        DSIPolicyCase(
            "tn_single_entry_lists",
            "TN",
            _a(intended_users=["nurse practitioner"], cautioned_out_of_scope_uses=["research use"]),
            _r(),
            True,
            "one real entry is enough for the list fields",
        )
    )

    # --- true positives: exactly one required attribute missing, plus unknown dsi_id ---

    cases.append(
        DSIPolicyCase(
            "tp_unknown_dsi_id",
            "TP",
            None,
            _r(dsi_id="ghost"),
            False,
            "no registration exists for this dsi_id",
        )
    )

    for field in _REQUIRED_FIELDS_TEXT:
        cases.append(
            DSIPolicyCase(
                f"tp_missing_{field}",
                "TP",
                _a(**{field: None}),
                _r(),
                False,
                f"{field} unset",
            )
        )

    for field in _REQUIRED_FIELDS_ENUM:
        cases.append(
            DSIPolicyCase(
                f"tp_missing_{field}",
                "TP",
                _a(**{field: None}),
                _r(),
                False,
                f"{field} unset",
            )
        )

    for field in _REQUIRED_FIELDS_LIST:
        cases.append(
            DSIPolicyCase(
                f"tp_missing_{field}",
                "TP",
                _a(**{field: []}),
                _r(),
                False,
                f"{field} empty",
            )
        )

    # --- edge cases ---

    cases.append(
        DSIPolicyCase(
            "edge_whitespace_only_field",
            "edge",
            _a(developer_name="   "),
            _r(),
            False,
            "whitespace-only string is not a real disclosure",
        )
    )
    cases.append(
        DSIPolicyCase(
            "edge_list_with_only_blank_entries",
            "edge",
            _a(intended_users=["  ", ""]),
            _r(),
            False,
            "a list of blank strings is not a real disclosure",
        )
    )
    cases.append(
        DSIPolicyCase(
            "edge_list_with_one_real_entry_among_blanks",
            "edge",
            _a(intended_users=["  ", "physician", ""]),
            _r(),
            True,
            "one non-blank entry is enough even alongside blank ones",
        )
    )

    # --- adversarial ---

    cases.append(
        DSIPolicyCase(
            "adversarial_multiple_missing_fields_at_once",
            "adversarial",
            _a(developer_name=None, output_type=None, cautioned_out_of_scope_uses=[]),
            _r(),
            False,
            "three separate required fields missing simultaneously",
        )
    )
    cases.append(
        DSIPolicyCase(
            "adversarial_thorough_looking_registration_missing_one_required_field",
            "adversarial",
            _a(
                known_risks_and_limitations=None,
                input_features=["age", "lactate", "heart_rate"],
                same_source_validity="AUROC 0.81 on internal holdout",
                external_validity="AUROC 0.77 on partner health system data",
                fairness_approach="subgroup AUROC parity check across sex and age band",
            ),
            _r(),
            False,
            "depth on categories 4/5/7 doesn't substitute for a missing category 3 field",
        )
    )
    cases.append(
        DSIPolicyCase(
            "adversarial_reregistration_overwrites_previous_complete_record",
            "adversarial",
            _a(developer_contact=None),
            _r(),
            False,
            "no versioning - the latest registration for a dsi_id is the only one evaluated",
        )
    )

    return cases
