"""
PolicyService implementation for Phase 2.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.policy.dsi_models import DSIAdvisoryDecision, DSIAdvisoryRequest, DSISourceAttributes
from app.policy.models import (
    ConsentRecord,
    OrgType,
    PHIExchangeDecision,
    PHIExchangeRequest,
    PolicyDecision,
    PurposeOfUse,
)


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

    # --- HIE / PHI exchange config (Section 5.1.3 scenario) ---
    #
    # HIE participant directory. In a real deployment this would come from
    # a participant onboarding service; here it is static seed data, same
    # spirit as _TENANT_PROVIDER_MAP above.
    _HIE_PARTICIPANTS: dict[str, OrgType] = {
        "hie_hospital_north": OrgType.HOSPITAL,
        "hie_clinic_riverside": OrgType.CLINIC,
        "hie_payer_horizon": OrgType.PAYER,
        "hie_research_lab": OrgType.RESEARCH_ORG,
    }

    # Purpose-of-use an org type may invoke regardless of what a patient's
    # consent grants. A payer asking for "treatment" data should fail here
    # even if a mis-scoped consent record somehow grants it — this is the
    # defense-in-depth layer, consent is the other one.
    _ORG_TYPE_ALLOWED_PURPOSES: dict[OrgType, set[PurposeOfUse]] = {
        OrgType.HOSPITAL: {
            PurposeOfUse.TREATMENT,
            PurposeOfUse.HEALTHCARE_OPERATIONS,
            PurposeOfUse.PUBLIC_HEALTH,
            PurposeOfUse.PATIENT_REQUEST,
        },
        OrgType.CLINIC: {
            PurposeOfUse.TREATMENT,
            PurposeOfUse.HEALTHCARE_OPERATIONS,
            PurposeOfUse.PATIENT_REQUEST,
        },
        OrgType.PAYER: {
            PurposeOfUse.PAYMENT,
            PurposeOfUse.HEALTHCARE_OPERATIONS,
        },
        OrgType.RESEARCH_ORG: {
            PurposeOfUse.RESEARCH,
        },
    }

    # Categories sensitive enough that TPO-style purposes aren't enough on
    # their own — loosely modeled on the extra handling 42 CFR Part 2 gives
    # substance use records, not a verified implementation of it. Sharing
    # still requires the purpose to be treatment or a direct patient
    # request, on top of whatever the consent record otherwise grants.
    _RESTRICTED_CATEGORIES = {"mental_health", "substance_use"}
    _RESTRICTED_CATEGORY_PURPOSES = {PurposeOfUse.TREATMENT, PurposeOfUse.PATIENT_REQUEST}

    # --- Predictive DSI transparency (HTI-1, 45 CFR 170.315(b)(11)) ---
    #
    # Only categories 1-3 (identity/output, purpose, cautioned use) gate
    # whether a DSI-influenced output can be finalized. Categories 4 and 7
    # are captured on DSISourceAttributes but not checked here; 5, 6, 8, 9
    # aren't checked at all in this pass. See docs/dsi_transparency_governance.md.
    _REQUIRED_DSI_TEXT_FIELDS = (
        "developer_name",
        "developer_contact",
        "funding_source",
        "output_value_description",
        "intended_use",
        "intended_patient_population",
        "known_risks_and_limitations",
    )
    _REQUIRED_DSI_LIST_FIELDS = (
        "intended_users",
        "cautioned_out_of_scope_uses",
    )
    _REQUIRED_DSI_ENUM_FIELDS = (
        "output_type",
        "decision_making_role",
    )

    def __init__(self, policy_suite_version: str = "v1"):
        self.policy_suite_version = policy_suite_version
        self._policies = self._load_policies()
        self._consents: dict[str, ConsentRecord] = {}
        self._hie_participants: dict[str, OrgType] = dict(self._HIE_PARTICIPANTS)
        self._dsi_registrations: dict[str, DSISourceAttributes] = {}

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

    # --- HIE / PHI exchange evaluation ---

    def register_consent(self, consent: ConsentRecord) -> None:
        self._consents[consent.consent_id] = consent

    def register_hie_participant(self, org_id: str, org_type: OrgType) -> None:
        self._hie_participants[org_id] = org_type

    def evaluate_phi_exchange(self, request: PHIExchangeRequest) -> PHIExchangeDecision:
        """Consent-scope and purpose-of-use check for one HIE disclosure.

        Every branch below denies for a distinct, independently testable
        reason so a caller (and the evaluation suite) can tell which rule
        fired. Order matters: identity and lifecycle checks on the consent
        record run before anything that depends on its contents being
        trustworthy.
        """
        policies_applied: list[str] = []

        def denied(reason: str) -> PHIExchangeDecision:
            return PHIExchangeDecision(
                allowed=False,
                reason=reason,
                tenant_id=request.disclosing_org,
                policies_applied=policies_applied,
                policy_suite_version=self.policy_suite_version,
                consent_id=request.consent_id,
                purpose_of_use=request.purpose_of_use,
                phi_categories=sorted(request.categories),
                disclosing_org=request.disclosing_org,
                receiving_org=request.receiving_org,
                timestamp=datetime.now(UTC),
            )

        consent = self._consents.get(request.consent_id)
        policies_applied.append("consent_lookup")
        if consent is None:
            return denied(f"No consent record found for consent_id '{request.consent_id}'")

        policies_applied.append("consent_identity_check")
        if consent.patient_id != request.patient_id:
            return denied(
                f"consent_id '{request.consent_id}' does not belong to patient "
                f"'{request.patient_id}'"
            )

        policies_applied.append("consent_status_check")
        if consent.revoked:
            return denied(f"Consent '{request.consent_id}' has been revoked")

        if consent.expires_at is not None:
            now = datetime.now(UTC)
            expires_at = consent.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if now >= expires_at:
                return denied(f"Consent '{request.consent_id}' expired at {expires_at.isoformat()}")

        policies_applied.append("hie_participant_check")
        org_type = self._hie_participants.get(request.receiving_org)
        if org_type is None:
            return denied(f"'{request.receiving_org}' is not a registered HIE participant")

        policies_applied.append("org_purpose_policy")
        if request.purpose_of_use not in self._ORG_TYPE_ALLOWED_PURPOSES[org_type]:
            return denied(
                f"Org type '{org_type.value}' is not authorized for purpose "
                f"'{request.purpose_of_use.value}'"
            )

        policies_applied.append("consent_purpose_policy")
        if request.purpose_of_use not in consent.granted_purposes:
            return denied(
                f"Consent '{request.consent_id}' does not authorize purpose "
                f"'{request.purpose_of_use.value}'"
            )

        policies_applied.append("consent_recipient_policy")
        if "*" not in consent.authorized_recipients and (
            request.receiving_org not in consent.authorized_recipients
        ):
            return denied(
                f"Consent '{request.consent_id}' does not authorize disclosure to "
                f"'{request.receiving_org}'"
            )

        policies_applied.append("consent_category_policy")
        uncovered = request.categories - consent.granted_categories
        if uncovered:
            return denied(
                f"Consent '{request.consent_id}' does not cover categories: "
                f"{sorted(c.value for c in uncovered)}"
            )

        policies_applied.append("restricted_category_policy")
        restricted_requested = {c.value for c in request.categories} & self._RESTRICTED_CATEGORIES
        if restricted_requested and request.purpose_of_use not in self._RESTRICTED_CATEGORY_PURPOSES:
            return denied(
                f"Categories {sorted(restricted_requested)} require a treatment or "
                f"patient_request purpose; got '{request.purpose_of_use.value}'"
            )

        return PHIExchangeDecision(
            allowed=True,
            reason="Consent scope and purpose of use both authorize this disclosure",
            tenant_id=request.disclosing_org,
            policies_applied=policies_applied,
            policy_suite_version=self.policy_suite_version,
            consent_id=request.consent_id,
            purpose_of_use=request.purpose_of_use,
            phi_categories=sorted(request.categories),
            disclosing_org=request.disclosing_org,
            receiving_org=request.receiving_org,
            timestamp=datetime.now(UTC),
        )

    # --- Predictive DSI transparency evaluation ---

    def register_dsi(self, attributes: DSISourceAttributes) -> None:
        self._dsi_registrations[attributes.dsi_id] = attributes

    def _missing_dsi_attributes(self, attrs: DSISourceAttributes) -> list[str]:
        missing = []
        for field in self._REQUIRED_DSI_TEXT_FIELDS:
            value = getattr(attrs, field)
            if value is None or not value.strip():
                missing.append(field)
        for field in self._REQUIRED_DSI_LIST_FIELDS:
            values: list[str] = getattr(attrs, field)
            if not any(v.strip() for v in values):
                missing.append(field)
        for field in self._REQUIRED_DSI_ENUM_FIELDS:
            if getattr(attrs, field) is None:
                missing.append(field)
        return missing

    def evaluate_dsi_output(self, request: DSIAdvisoryRequest) -> DSIAdvisoryDecision:
        """Gate a DSI-influenced output on HTI-1 categories 1-3 being present.

        This does not evaluate the model's accuracy, fairness, or clinical
        safety - it checks whether the transparency attributes required at
        the point of use are actually attached to the DSI registration.
        Those are different problems; this only covers the second one.
        """
        attrs = self._dsi_registrations.get(request.dsi_id)

        if attrs is None:
            return DSIAdvisoryDecision(
                allowed=False,
                reason=f"No DSI registration found for dsi_id '{request.dsi_id}'",
                tenant_id=request.requesting_org,
                policies_applied=["dsi_registration_lookup"],
                policy_suite_version=self.policy_suite_version,
                dsi_id=request.dsi_id,
                timestamp=datetime.now(UTC),
            )

        missing = self._missing_dsi_attributes(attrs)
        if missing:
            return DSIAdvisoryDecision(
                allowed=False,
                reason=(
                    f"DSI '{request.dsi_id}' is missing required transparency "
                    f"attributes: {missing}"
                ),
                tenant_id=request.requesting_org,
                policies_applied=["dsi_registration_lookup", "dsi_required_attribute_check"],
                policy_suite_version=self.policy_suite_version,
                dsi_id=request.dsi_id,
                output_type=attrs.output_type,
                decision_making_role=attrs.decision_making_role,
                missing_attributes=missing,
                timestamp=datetime.now(UTC),
            )

        return DSIAdvisoryDecision(
            allowed=True,
            reason="Required transparency attributes (categories 1-3) are present",
            tenant_id=request.requesting_org,
            policies_applied=["dsi_registration_lookup", "dsi_required_attribute_check"],
            policy_suite_version=self.policy_suite_version,
            dsi_id=request.dsi_id,
            output_type=attrs.output_type,
            decision_making_role=attrs.decision_making_role,
            timestamp=datetime.now(UTC),
        )
