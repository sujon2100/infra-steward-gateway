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
  policy/                     PolicyService and decision models
  providers/                  AbstractAIProvider, registry, stubs
  supervisory/                Simulated supervisory reporting service
  workflow/                   Engine, request metadata, event bus
  evidence/                   Evidence record service and producer
  observability/              Prometheus metrics
  main.py                     FastAPI entry point

go/evidence_ingester/         Go ingester (persists evidence asynchronously)

tests/                        Python test suite (pytest)
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

## License

Prototype developed as a master's thesis artefact at DSV, Stockholm
University. See `LICENSE` if present.
