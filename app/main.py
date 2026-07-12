"""
InfraSteward Gateway FastAPI Application.

Entry point for the law-aware integration governance gateway.
Exposes health, info, and metrics endpoints; routes governance workflows.
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import generate_latest

from app import __version__
from app.config import Settings
from app.evidence.producer import EvidenceProducer
from app.observability.metrics import (
    gateway_request_latency_seconds,
    gateway_requests_total,
)
from app.policy.models import ConsentRecord, PHIExchangeRequest
from app.workflow.request_metadata import ReportRequest
from app.workflow.scenarios import ScenarioRunner

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Application state
settings = Settings()
startup_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore
    """
    Application lifecycle management (startup/shutdown).

    Args:
        app: FastAPI application instance.

    Yields:
        Control during application running.
    """
    logger.info("InfraSteward Gateway starting (v%s)", __version__)
    yield
    logger.info("InfraSteward Gateway shutting down")


app = FastAPI(
    title="InfraSteward Gateway",
    description="Law-aware integration governance gateway for regulated AI workflows",
    version=__version__,
    lifespan=lifespan,
)


@app.middleware("http")
async def request_metrics_middleware(request: Request, call_next):  # type: ignore
    """
    Middleware to collect request metrics and logs.

    Records request latency, counts, and adds request_id to logs.

    Args:
        request: Incoming request.
        call_next: Next middleware/handler.

    Returns:
        Response with metrics recorded.
    """
    start_time = time.time()

    try:
        response = await call_next(request)
        duration = time.time() - start_time

        gateway_request_latency_seconds.labels(
            method=request.method,
            endpoint=request.url.path,
        ).observe(duration)
        gateway_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status=str(response.status_code),
        ).inc()

        logger.info(
            "request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_seconds": duration,
            },
        )
        return response
    except Exception as exc:
        duration = time.time() - start_time

        gateway_request_latency_seconds.labels(
            method=request.method,
            endpoint=request.url.path,
        ).observe(duration)
        gateway_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status="500",
        ).inc()

        logger.error(
            "request failed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "error": str(exc),
                "duration_seconds": duration,
            },
        )
        raise


@app.get("/health")
async def health() -> JSONResponse:
    """
    Health check endpoint for liveness and readiness probes.

    Returns:
        JSON response with health status.
    """
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "version": __version__,
            "uptime_seconds": time.time() - startup_time,
        },
    )


@app.get("/info")
async def info() -> JSONResponse:
    """
    Information endpoint with build and runtime details.

    Returns:
        JSON response with gateway info.
    """
    return JSONResponse(
        status_code=200,
        content={
            "service": "InfraSteward Gateway",
            "version": __version__,
            "environment": settings.environment,
            "log_level": settings.log_level,
            "uptime_seconds": time.time() - startup_time,
        },
    )


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    """
    Prometheus metrics endpoint.

    Returns:
        Prometheus-format metrics in plain text.
    """
    return PlainTextResponse(content=generate_latest(), media_type="text/plain")


@app.get("/")
async def root() -> JSONResponse:
    """
    Root endpoint.

    Returns:
        JSON response with service description.
    """
    return JSONResponse(
        status_code=200,
        content={
            "service": "InfraSteward Gateway",
            "version": __version__,
            "endpoints": {
                "health": "/health",
                "info": "/info",
                "metrics": "/metrics",
                "reports": "/reports (POST)",
            },
        },
    )


# Singleton services for Phase 2 integration.
policy_service = None
evidence_producer = None
evidence_service = None
workflow_engine = None
scenario_runner = None
phi_exchange_coordinator = None

try:
    from app.evidence.producer import EvidenceProducer
    from app.evidence.service import EvidenceService
    from app.policy.service import PolicyService
    from app.providers.registry import ProviderRegistry
    from app.providers.stub import StubAIProvider
    from app.providers.stub_b import StubAIProviderB
    from app.supervisory.service import SupervisoryReportingService
    from app.tenants.context_manager import TenantContextManager
    from app.workflow.engine import WorkflowEngine
    from app.workflow.events import EventBus
    from app.workflow.phi_exchange import PHIExchangeCoordinator

    evidence_producer = EvidenceProducer(settings)
    evidence_service = EvidenceService(evidence_producer)
    policy_service = PolicyService()

    provider_registry = ProviderRegistry(default_name="stub_a")
    provider_registry.register("stub_a", StubAIProvider())
    provider_registry.register("stub_b", StubAIProviderB())

    tenant_context_manager = TenantContextManager()
    supervisory_service = SupervisoryReportingService()
    event_bus = EventBus()

    workflow_engine = WorkflowEngine(
        policy_service,
        evidence_service,
        provider_registry=provider_registry,
        tenant_context_manager=tenant_context_manager,
        supervisory_service=supervisory_service,
        event_bus=event_bus,
    )
    scenario_runner = ScenarioRunner(workflow_engine)
    phi_exchange_coordinator = PHIExchangeCoordinator(policy_service, evidence_service, event_bus)
except Exception:
    policy_service = None
    evidence_producer = None
    evidence_service = None
    workflow_engine = None
    scenario_runner = None
    phi_exchange_coordinator = None


@app.get("/evidence/{request_id}")
async def get_evidence(request_id: str) -> JSONResponse:
    """
    Retrieve evidence record by request_id.
    """
    if evidence_service is None:
        return JSONResponse(status_code=500, content={"error": "Evidence service not initialized"})

    record = evidence_service.get_record(request_id)
    if record is None:
        return JSONResponse(status_code=404, content={"error": "Record not found"})

    return JSONResponse(status_code=200, content=jsonable_encoder(record))


@app.post("/reports")
async def submit_report(report_request: ReportRequest) -> JSONResponse:
    """
    Submit a report to the workflow engine for policy evaluation and AI enrichment.
    """
    if workflow_engine is None:
        return JSONResponse(status_code=500, content={"error": "Workflow engine not initialized"})

    result = await workflow_engine.process_report(report_request.dict())
    logger.info(
        "processed report",
        extra={
            "request_id": result.get("request_id"),
            "tenant_id": result.get("tenant_id"),
            "status": result.get("status"),
        },
    )

    return JSONResponse(status_code=200, content=result)


@app.get("/scenarios/bank-alpha/compliant")
async def scenario_bank_alpha_compliant() -> JSONResponse:
    if scenario_runner is None:
        return JSONResponse(status_code=500, content={"error": "Scenario runner not initialized"})

    result = await scenario_runner.run_bank_alpha_compliant()
    return JSONResponse(status_code=200, content=result)


@app.get("/scenarios/bank-beta/blocked")
async def scenario_bank_beta_blocked() -> JSONResponse:
    if scenario_runner is None:
        return JSONResponse(status_code=500, content={"error": "Scenario runner not initialized"})

    result = await scenario_runner.run_bank_beta_blocked()
    return JSONResponse(status_code=200, content=result)


@app.get("/scenarios/bank-alpha/provider-failure")
async def scenario_bank_alpha_provider_failure() -> JSONResponse:
    if scenario_runner is None:
        return JSONResponse(status_code=500, content={"error": "Scenario runner not initialized"})

    result = await scenario_runner.run_bank_alpha_provider_failure()
    return JSONResponse(status_code=200, content=result)


@app.post("/consents")
async def register_consent(consent: ConsentRecord) -> JSONResponse:
    """
    Register a patient consent record against which future PHI exchange
    requests are checked. There is no revocation-notification flow, no
    versioning, and no identity proofing here — this is a policy-input
    endpoint, not a consent management system.
    """
    if policy_service is None:
        return JSONResponse(status_code=500, content={"error": "Policy service not initialized"})

    policy_service.register_consent(consent)
    return JSONResponse(
        status_code=201,
        content={"status": "registered", "consent_id": consent.consent_id},
    )


@app.post("/phi-exchanges")
async def submit_phi_exchange(request: PHIExchangeRequest) -> JSONResponse:
    """
    Evaluate one HIE disclosure against consent scope and purpose of use,
    and record the consent basis in the evidence store either way.
    """
    if phi_exchange_coordinator is None:
        return JSONResponse(
            status_code=500, content={"error": "PHI exchange coordinator not initialized"}
        )

    result = await phi_exchange_coordinator.process(request)
    logger.info(
        "processed phi exchange",
        extra={
            "request_id": result["request_id"],
            "disclosing_org": request.disclosing_org,
            "receiving_org": request.receiving_org,
            "allowed": result["decision"]["allowed"],
        },
    )
    return JSONResponse(status_code=200, content=result)


# Placeholder for /reports endpoint (Phase 3)
# @app.post("/reports")
# async def submit_report(request: SubmitReportRequest) -> JSONResponse:
#     """Submit a report for processing through the governance gateway."""
#     pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )
