# InfraSteward Gateway

A law-aware AI workflow gateway prototype for multi-tenant, event-driven
integration platforms in regulated environments. Developed as the artefact
for a master's thesis at the Department of Computer and Systems Sciences
(DSV), Stockholm University.

The gateway sits between an external API and the platform's AI and
workflow services. For every request it resolves the tenant context,
evaluates a policy-as-code rule set (including jurisdiction), routes to a
registered AI provider, captures a structured evidence record, and
forwards the enriched report to a simulated supervisory reporting service.
A separate Go microservice persists evidence records asynchronously, and
Prometheus and Grafana provide observability.

## Repository layout

```
app/                          Python gateway (FastAPI)
  tenants/                    TenantContextManager
  policy/                     PolicyService and decision models (banking + HIE/PHI)
  providers/                  AbstractAIProvider, registry, stubs
  supervisory/                Simulated supervisory reporting service
  workflow/                   Engine, request metadata, event bus, PHI exchange coordinator
  evidence/                   Evidence record service and producer
  observability/              Prometheus metrics
  main.py                     FastAPI entry point

go/evidence_ingester/         Go ingester (persists evidence asynchronously)

tests/                        Python test suite (pytest)
evaluation/                   Accuracy and latency evaluation for the PHI policy
docs/                         Design notes
ops/observability/            Prometheus + Grafana config
ops/k8s/                      Kubernetes manifests
ops/tekton/                   Tekton pipeline for CI
docker-compose.yaml           Local Prometheus + Grafana stack
```

## Prerequisites

- Python 3.12
- Go 1.21
- Docker (for Prometheus and Grafana)

## Setup

```bash
git clone https://github.com/sujon2100/infra-steward-gateway.git
cd infra-steward-gateway

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running locally

The gateway, the ingester, and the observability stack each run in their
own terminal.

```bash
# Terminal 1 — Python gateway on port 8000
source .venv/bin/activate
PYTHONPATH=. python -m app.main

# Terminal 2 — Go evidence ingester on port 8081
cd go/evidence_ingester
go run .

# Terminal 3 — Prometheus + Grafana
docker compose up -d
```

Once all three are up:

- Gateway: <http://localhost:8000>
- Ingester: <http://localhost:8081>
- Prometheus: <http://localhost:9090>
- Grafana: <http://localhost:3000> (admin / admin)

In Grafana, add Prometheus as a data source
(`http://host.docker.internal:9090`) and import the dashboard from
`ops/observability/grafana-dashboard.json`.

## Submitting a request

```bash
curl -X POST http://127.0.0.1:8000/reports \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "bank_alpha",
    "scenario": "reporting",
    "report_id": "demo-1",
    "report_type": "standard",
    "payload": {"text": "monthly summary"}
  }'
```

The response includes the policy decision, the selected provider, the
enriched payload, and the supervisory submission acknowledgement. The
full evidence record is retrievable at:

```bash
curl http://127.0.0.1:8000/evidence/<request_id>
```

The same record is also available from the ingester on port 8081 once it
has been persisted asynchronously.

## Tests

```bash
source .venv/bin/activate
pytest -v
mypy app
ruff check app tests
(cd go/evidence_ingester && go test ./...)
```

The Tekton pipeline in `ops/tekton/` runs the same sequence in a clean
Kubernetes container.

The PHI policy accuracy and latency evaluation in `evaluation/` isn't
part of that gate — it's a reporting script, not a correctness test
(though `tests/test_phi_policy_evaluation.py` does assert the accuracy
dataset stays at zero false positives/negatives). Run it directly:

```bash
pip install -e ".[dev]"   # pulls in scipy/numpy for the latency stats
PYTHONPATH=. python evaluation/phi_policy_accuracy.py
PYTHONPATH=. python evaluation/phi_policy_latency.py
```

## Tenants and providers in the prototype

| Tenant         | Jurisdiction | Provider key | Provider class      |
|----------------|--------------|--------------|---------------------|
| `bank_alpha`   | EU           | `stub_a`     | `StubAIProvider`    |
| `bank_beta`    | EU           | `stub_b`     | `StubAIProviderB`   |
| `bank_mars`    | US           | `stub_a`     | `StubAIProvider`    |
| `bank_neptune` | APAC         | `stub_b`     | `StubAIProviderB`   |

`bank_beta` is configured to allow only the `analysis` scenario and to
reject the `sensitive` and `confidential` report types. Submitting a
report from a jurisdiction other than a tenant's home jurisdiction is
denied by the jurisdiction check in `PolicyService`.

## HIPAA PHI exchange governance (HIE scenario)

`feature/hipaa-phi-governance` extends `PolicyService` with a consent-scope
and purpose-of-use check for a regional Health Information Exchange
routing PHI between hospitals, clinics, and payers. See
[`docs/hipaa_phi_governance.md`](docs/hipaa_phi_governance.md) for what's
implemented versus still conceptual, and `evaluation/` for the accuracy
and latency evaluation.

Register a consent, then attempt a disclosure against it:

```bash
curl -X POST http://127.0.0.1:8000/consents \
  -H 'Content-Type: application/json' \
  -d '{
    "consent_id": "demo-consent-1",
    "patient_id": "demo-patient-1",
    "granted_categories": ["diagnosis"],
    "granted_purposes": ["treatment"],
    "authorized_recipients": ["hie_hospital_north"]
  }'

curl -X POST http://127.0.0.1:8000/phi-exchanges \
  -H 'Content-Type: application/json' \
  -d '{
    "consent_id": "demo-consent-1",
    "patient_id": "demo-patient-1",
    "disclosing_org": "hie_clinic_riverside",
    "receiving_org": "hie_hospital_north",
    "categories": ["diagnosis"],
    "purpose_of_use": "treatment"
  }'
```

Registered HIE participants in the prototype: `hie_hospital_north`
(hospital), `hie_clinic_riverside` (clinic), `hie_payer_horizon` (payer),
`hie_research_lab` (research org). Org type gates purpose of use
independently of consent — a payer will never clear a `treatment`
request, for example, even if a mis-scoped consent record grants it.

## License

Prototype developed as a master's thesis artefact at DSV, Stockholm
University. See `LICENSE` if present.
