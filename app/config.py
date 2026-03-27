"""
Configuration and settings for InfraSteward Gateway.

Uses Pydantic v2 for environment-based configuration.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Gateway configuration loaded from environment variables.

    Example:
        HOST=0.0.0.0 PORT=8000 ENVIRONMENT=production python -m app.main
    """

    # Server
    host: str = Field(default="127.0.0.1", description="Server host")
    port: int = Field(default=8000, description="Server port")
    environment: str = Field(
        default="development",
        description="Environment (development, staging, production)",
    )
    log_level: str = Field(default="INFO", description="Logging level")

    # Governance
    tenant_default: str | None = Field(default=None, description="Default tenant ID")
    policy_default_strict: bool = Field(
        default=True, description="Enforce policies strictly by default"
    )

    # AI Provider (Phase 2+)
    provider_default: str = Field(default="stub", description="Default AI provider")
    provider_timeout_seconds: float = Field(default=30.0, description="Provider request timeout")

    # Evidence & Observability
    evidence_ingester_uri: str = Field(
        default="http://localhost:8081",
        description="Evidence ingester service URI",
    )
    metrics_enabled: bool = Field(default=True, description="Enable Prometheus metrics")

    class Config:
        """Pydantic config."""

        env_file = ".env"
        case_sensitive = False

    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"Settings(host={self.host}, port={self.port}, "
            f"environment={self.environment}, provider={self.provider_default})"
        )
