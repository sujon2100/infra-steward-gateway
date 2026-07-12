"""
Predictive DSI transparency models (ONC/ASTP HTI-1, 45 CFR 170.315(b)(11)).

Split out of models.py rather than added to it — that file already carries
the banking policy models and the PHI/HIE models, and a third unrelated
schema on top of those two was starting to make it hard to find anything.

Field names below track the source-attribute categories as HTI-1 groups
them, not the full enumerated list of 31 attributes one-for-one. Categories
1-4 and 7 get real structured fields; 5, 6, 8, and 9 get a handful of
free-text fields so the schema can hold something if it's captured, but
nothing in this pass enforces their presence.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.policy.models import PolicyDecision


class DSIOutputType(StrEnum):
    PREDICTION = "prediction"
    CLASSIFICATION = "classification"
    RECOMMENDATION = "recommendation"
    EVALUATION = "evaluation"
    ANALYSIS = "analysis"
    OTHER = "other"


class DSIDecisionRole(StrEnum):
    INFORMS = "informs"
    AUGMENTS = "augments"
    REPLACES = "replaces"


class DSISourceAttributes(BaseModel):
    dsi_id: str = Field(..., min_length=1)
    model_name: str = Field(..., min_length=1)

    # Category 1: details and output of the intervention.
    developer_name: str | None = None
    developer_contact: str | None = None
    funding_source: str | None = None
    output_value_description: str | None = None
    output_type: DSIOutputType | None = None

    # Category 2: purpose of the intervention.
    intended_use: str | None = None
    intended_patient_population: str | None = None
    intended_users: list[str] = Field(default_factory=list)
    decision_making_role: DSIDecisionRole | None = None

    # Category 3: cautioned out-of-scope use.
    cautioned_out_of_scope_uses: list[str] = Field(default_factory=list)
    known_risks_and_limitations: str | None = None

    # Category 4: development details and input features.
    training_data_inclusion_criteria: str | None = None
    training_data_exclusion_criteria: str | None = None
    input_features: list[str] = Field(default_factory=list)
    training_data_demographic_representativeness: str | None = None
    training_data_relevance_to_deployment: str | None = None

    # Category 5: process used to ensure fairness (schema only, not enforced).
    fairness_approach: str | None = None
    bias_mitigation_methods: str | None = None

    # Category 6: external validation process (schema only, not enforced).
    external_validation_data_source: str | None = None
    external_validation_conducted_by: str | None = None
    external_validation_demographic_representativeness: str | None = None
    external_validation_process_description: str | None = None

    # Category 7: quantitative measures of performance.
    same_source_validity: str | None = None
    same_source_fairness: str | None = None
    external_validity: str | None = None
    external_fairness: str | None = None
    outcome_evaluation_references: list[str] = Field(default_factory=list)

    # Category 8: ongoing maintenance (schema only, not enforced).
    validity_monitoring_process: str | None = None
    local_validity_notes: str | None = None
    fairness_monitoring_process: str | None = None
    local_fairness_notes: str | None = None

    # Category 9: update and continued validation schedule (schema only).
    update_process: str | None = None
    correction_process: str | None = None


class DSIAdvisoryRequest(BaseModel):
    dsi_id: str = Field(..., min_length=1)
    requesting_org: str = Field(..., min_length=1)
    encounter_id: str = Field(..., min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class DSIAdvisoryDecision(PolicyDecision):
    dsi_id: str | None = None
    output_type: DSIOutputType | None = None
    decision_making_role: DSIDecisionRole | None = None
    missing_attributes: list[str] = Field(default_factory=list)
