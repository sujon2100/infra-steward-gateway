# HIPAA PHI exchange governance (HIE scenario, Phase 2 extension)

Status: implemented and tested on `feature/hipaa-phi-governance`, branched
from `v0.1.0-thesis-validated`. Not merged to `main`, not deployed.

This extends `PolicyService` with a second decision path for the regional
Health Information Exchange scenario described in the business plan
(Section 5.1.3): hospitals, clinics, and payers exchanging PHI under
consent and purpose-of-use constraints. It does not replace the existing
banking/jurisdiction policy path — `evaluate()` is untouched, and
`evaluate_phi_exchange()` sits next to it on the same service.

## What's implemented

- **PHI data classification** — `PHICategory` enum (`app/policy/models.py`):
  demographic, diagnosis, medication, lab_result, mental_health,
  substance_use, genetic. Coarse classification, not a data-element level
  taxonomy.
- **Purpose-of-use validation** — `PurposeOfUse` enum: treatment, payment,
  healthcare_operations, public_health, research, patient_request.
  Checked twice in `evaluate_phi_exchange`: once against what the
  receiving org's type is ever allowed to invoke (`_ORG_TYPE_ALLOWED_PURPOSES`,
  independent of any consent), and once against what the specific consent
  record grants.
- **Consent-scope checks** — `ConsentRecord` model: existence, patient
  binding, revocation, expiry, authorized-recipient list, category
  coverage. All nine checks in `evaluate_phi_exchange` deny for a distinct
  reason so a caller can tell which rule fired; order matters (identity
  and lifecycle checks run before anything that trusts the record's
  contents).
- **Restricted-category rule** — `mental_health` and `substance_use`
  additionally require the purpose to be treatment or patient_request,
  regardless of what else the consent grants. This is loosely modeled on
  how 42 CFR Part 2 treats substance-use records more strictly than
  general HIPAA TPO use — it is not a verified implementation of Part 2.
  There's no distinction between a qualifying SUD program record and an
  ordinary mental-health note, no "written consent to redisclose"
  handling, none of the actual regulatory detail. Treat it as "some
  categories need a tighter purpose check," not a compliance claim.
- **Evidence capture** — `EvidenceRecord` gained `consent_id`,
  `purpose_of_use`, `phi_categories`, `disclosing_org`, `receiving_org`.
  `EvidenceService.start_phi_exchange_record` seeds them up front (unlike
  the banking flow, a PHI exchange has its consent basis before the
  policy check even runs). `PHIExchangeCoordinator` records a
  `CONSENT_EVALUATED` event and finalizes the record the same way the
  banking flow finalizes. The Go evidence ingester's domain struct was
  extended with the matching fields — without that change it would have
  silently dropped them, since Go's `encoding/json` ignores unknown
  fields on decode by default.
- **API** — `POST /consents` registers a `ConsentRecord`; `POST
  /phi-exchanges` evaluates one disclosure and returns the decision.
- **HIE participant directory** — four seeded participants
  (`hie_hospital_north`, `hie_clinic_riverside`, `hie_payer_horizon`,
  `hie_research_lab`), same static-seed-data pattern as the existing
  tenant/provider mappings.

## What's not implemented (still conceptual)

- No real consent management integration. Consents are registered
  through a plain API call — no identity proofing, no link to an actual
  MPI, no revocation propagation from an external system, no versioning.
- No "minimum necessary" analysis. The category-coverage check confirms
  the request stays within what's granted; it does not evaluate whether
  the request is scoped as narrowly as the stated purpose requires.
- No legal review. The purpose-of-use taxonomy and the restricted-category
  rule are software modeling choices informed by a general reading of
  HIPAA's TPO structure and the existence of 42 CFR Part 2, not a legal
  compliance determination. Nothing here should be described as
  "HIPAA-compliant" — it enforces rules inspired by HIPAA concepts.
- No encryption at rest or in transit beyond whatever the base gateway
  already has, which is none in this prototype. PHI sits in-memory in the
  same unencrypted structures as the banking evidence records.
- No BAA modeling, no tamper-evidence on the evidence log itself — same
  limitation the base evidence store already has.
- No deployment. This branch has not been merged or deployed anywhere.

## Evaluation

Same methodology as the base gateway's RQ1/RQ2 evaluation.

**Accuracy** (`evaluation/phi_policy_accuracy.py`, dataset in
`evaluation/phi_policy_dataset.py`): confusion matrix over 48 hand-labeled
cases across four groups (true-negative/compliant, true-positive/violation,
edge, adversarial). Actual run: precision 1.0, recall 1.0, accuracy 1.0,
0 false positives, 0 false negatives — see
`evaluation/results/accuracy_report.md`. The important caveat, stated in
the report itself: expected labels were derived from the same
specification the implementation follows, written by the same person.
This measures spec conformance across a deliberately constructed case
set, not independent third-party validation, and a deterministic rule
engine scoring 100% here doesn't say anything about behavior on inputs
outside that set.

**Latency** (`evaluation/phi_policy_latency.py`): Kruskal-Wallis across
baseline / PHI-allow / PHI-deny paths, then pairwise Mann-Whitney U with a
Bonferroni-adjusted alpha, 3000 iterations per configuration. Actual run
found statistically significant pairwise differences (p < 1e-26) but the
practical median deltas were sub-microsecond (-1.00us to +0.05us) — see
`evaluation/results/latency_report.md`. Read that as: the added policy
check has no material latency cost relative to the existing banking
policy path, on this hardware, as a single-process microbenchmark with no
concurrent load. It is not a production capacity test.

New tests: `tests/test_policy_service_phi.py`,
`tests/test_phi_exchange_evidence.py`, `tests/test_phi_exchange_api.py`,
`tests/test_phi_policy_evaluation.py` — 28 tests, run alongside the
existing suite with `pytest -v`.

## Branching

This work is on `feature/hipaa-phi-governance`, branched from the tag
`v0.1.0-thesis-validated`, which marks the commit under academic
supervisor review. Any changes requested on that review belong on a
separate branch off the same tag (e.g. `fix/thesis-feedback`) so grading
feedback and this feature work stay independently mergeable.

## Deliberately out of scope here

Cloud deployment, independent uptime monitoring, and synthetic traffic
generation are the natural next step once this branch is reviewed and
merged, but are not part of this change. The working implementation and
its evaluation were the priority.
