# Predictive DSI transparency governance (HTI-1, 45 CFR 170.315(b)(11))

Status: implemented and tested on `feature/dsi-transparency-governance`,
branched from the tip of `feature/hipaa-phi-governance` (not from `main`,
not from the thesis-validated tag directly) because it reuses that
branch's evidence infrastructure. Not merged, not deployed.

## Regulatory grounding

ONC/ASTP's HTI-1 final rule (45 CFR 170.315(b)(11)) defines a "Predictive
Decision Support Intervention" as technology supporting a clinical
decision based on algorithms or models that derive relationships from
training data and produce a prediction, classification, recommendation,
evaluation, or other type of output. Certified health IT has to support
31 source attributes across 9 categories describing that DSI - who built
it, what it's for, where it shouldn't be used, how it was trained and
validated, how it's monitored and updated. Compliance was required by
December 31, 2024, with an ongoing maintenance-of-certification
obligation since January 1, 2025.

That's a real, binding, current requirement, and most vendors are still
working through it. What it is not is a model-validation problem - it's
an integration governance problem: making sure the disclosure information
about a DSI actually travels with its output and gets durably recorded
every time that output is used, across a stack where the model, the EHR,
and the system consuming the output can all be different vendors. That's
what this branch implements. It does not evaluate whether any given
model is accurate, fair, or clinically safe - a DSI can have every
required attribute filled in and still be a bad model. That's a separate,
harder problem this doesn't touch.

## What's implemented

- **`DSISourceAttributes`** (`app/policy/dsi_models.py`) - a registration
  record keyed by `dsi_id`, with real structured fields for categories 1,
  2, 3, 4, and 7:
  - Category 1 (details/output): `developer_name`, `developer_contact`,
    `funding_source`, `output_value_description`, `output_type`
    (prediction/classification/recommendation/evaluation/analysis/other).
  - Category 2 (purpose): `intended_use`, `intended_patient_population`,
    `intended_users`, `decision_making_role`
    (informs/augments/replaces).
  - Category 3 (cautioned use): `cautioned_out_of_scope_uses`,
    `known_risks_and_limitations`.
  - Category 4 (development/input features): `training_data_inclusion_criteria`,
    `training_data_exclusion_criteria`, `input_features`,
    `training_data_demographic_representativeness`,
    `training_data_relevance_to_deployment`.
  - Category 7 (quantitative performance): `same_source_validity`,
    `same_source_fairness`, `external_validity`, `external_fairness`,
    `outcome_evaluation_references`.

  Categories 5 (fairness process), 6 (external validation), 8 (ongoing
  monitoring), and 9 (update schedule) get a handful of free-text optional
  fields each, so the schema can hold something if it's captured - but
  nothing in this pass checks them. These are representative fields
  informed by the category descriptions, not a field-for-field
  transcription of all 31 named attributes.

- **Enforcement** - `PolicyService.evaluate_dsi_output` (extends the same
  service the banking and PHI checks live on) requires all eleven
  category 1-3 fields to be present before an output can be finalized.
  "Present" means a non-blank string for text fields, a non-None value for
  the two enum fields, and at least one non-blank entry for the two list
  fields - a list containing only whitespace strings is treated the same
  as an empty one. Missing anything returns every missing field name, not
  just the first one hit, since there's no meaningful "check order" here
  the way there is for the PHI consent rules.

- **Evidence capture** - `EvidenceRecord` gained `dsi_id`,
  `dsi_output_type`, `dsi_decision_making_role`, `dsi_missing_attributes`.
  Unlike the PHI exchange path, the transparency basis isn't known when
  the record is opened (it depends on a registration lookup that hasn't
  happened yet), so `EvidenceService.start_dsi_advisory_record` only seeds
  the identifiers and `record_dsi_transparency_basis` fills in the rest
  once the policy decision comes back. Go's domain struct was extended to
  match, same reasoning as the PHI branch - unknown fields get silently
  dropped on decode otherwise.

- **Where it's wired in** - `DSIAdvisoryCoordinator`
  (`app/workflow/dsi_advisory.py`) sits at the point the AI provider
  would actually produce an advisory output, reusing the existing
  `ProviderRegistry`/`AbstractAIProvider` abstraction rather than adding a
  parallel one. If the required attributes are missing, the provider is
  never invoked - there's no reason to spend an inference call on an
  output that can't be finalized, and it means "blocked" is a real state,
  not a display-layer suppression of something that already ran.

- **API** - `POST /dsi-registrations` registers a `DSISourceAttributes`
  record (incrementally - it doesn't need to be complete to register);
  `POST /dsi-advisories` evaluates one request against a `dsi_id` and
  returns the decision plus the advisory output, if any.

## What's not implemented / explicitly out of scope

- **Categories 5, 6, 8, 9 are schema-only.** The fields exist so something
  can be recorded, but nothing gates on them in this pass.
- **No model validation.** This governs whether the required transparency
  information is present and recorded - it says nothing about whether the
  model behind a `dsi_id` is actually accurate, fair, or clinically safe.
- **No per-DSI provider routing.** `dsi_id` identifies which registration
  to check, not which model runs. Every allowed advisory call in this
  prototype goes through whichever provider `ProviderRegistry` treats as
  default, regardless of which DSI was named.
- **No registration versioning.** Re-registering a `dsi_id` overwrites the
  previous record outright, with no history. A complete registration can
  be silently replaced by an incomplete one; this is exercised and
  documented in `tests/test_policy_service_dsi.py`, not hidden.
- **No legal or compliance review.** The mapping from HTI-1's category
  language to the specific field names above is a software modeling
  choice, not a certified reading of the rule text. Nothing here should
  be described as making a system "HTI-1 certified" or
  "45 CFR 170.315(b)(11) compliant" - it enforces a rule set informed by
  that regulation's structure.
- **No connection to actual ONC/CMS certification tooling** or a real
  Certified Health IT Product List entry. InfraSteward is a governance
  layer that would sit in front of certified health IT, not a
  certification artifact itself.
- **Same infrastructure-level gaps as the PHI branch** - no encryption at
  rest or in transit, no tamper-evidence on the evidence log, no
  deployment.

## Evaluation

Same methodology as `evaluation/phi_policy_accuracy.py`: a confusion
matrix over a hand-labeled case set (`evaluation/dsi_policy_dataset.py`),
grouped TN/TP/edge/adversarial. Actual run over 22 cases: precision 1.0,
recall 1.0, accuracy 1.0, 0 false positives, 0 false negatives - see
`evaluation/results/dsi_accuracy_report.md`. Same caveat as the PHI
report: labels were derived from the same spec the implementation
follows, by the same author, so this is spec-conformance, not
independent validation, and it doesn't say anything about the underlying
model's quality. No latency benchmark was built for this capability -
the request for this branch asked for the accuracy evaluation
specifically, and there wasn't a strong reason to assume the DSI check's
latency profile would look any different from the PHI check's already-
measured sub-microsecond overhead.

New tests: `tests/test_policy_service_dsi.py`,
`tests/test_dsi_advisory_evidence.py`, `tests/test_dsi_advisory_api.py`,
`tests/test_dsi_policy_evaluation.py` - 27 tests, run alongside the full
suite (99 total on this branch) with `pytest -v`.

## Branching

This work is on `feature/dsi-transparency-governance`, branched from the
tip of `feature/hipaa-phi-governance` rather than from `main` or the
`v0.1.0-thesis-validated` tag, because it extends that branch's evidence
schema and reuses its patterns directly. It stays its own branch so it
can be reviewed and merged independently of the PHI work. If a separate
thesis-feedback branch exists off the original tag, this branch does not
touch it or merge from it.
