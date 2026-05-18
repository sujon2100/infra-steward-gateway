"""
TenantContextManager — first step in the request lifecycle.

Resolves a raw tenant identifier (from the incoming request) into a
structured TenantContext. The context is propagated explicitly through
every subsequent step so cross-tenant contamination requires a coding
error rather than a silent omission.
"""

from __future__ import annotations

from app.tenants.models import TenantContext


class UnknownTenantError(KeyError):
    """Raised when the manager is asked for a tenant it does not recognise."""


class TenantContextManager:
    _REGISTRY: dict[str, TenantContext] = {
        "bank_alpha": TenantContext(
            tenant_id="bank_alpha",
            display_name="Bank Alpha",
            policy_scope="bank_alpha_policy",
            jurisdiction="EU",
        ),
        "bank_beta": TenantContext(
            tenant_id="bank_beta",
            display_name="Bank Beta",
            policy_scope="bank_beta_policy",
            jurisdiction="EU",
        ),
        "bank_mars": TenantContext(
            tenant_id="bank_mars",
            display_name="Bank Mars",
            policy_scope="bank_mars_policy",
            jurisdiction="US",
        ),
        "bank_neptune": TenantContext(
            tenant_id="bank_neptune",
            display_name="Bank Neptune",
            policy_scope="bank_neptune_policy",
            jurisdiction="APAC",
        ),
    }

    def resolve(self, tenant_id: str) -> TenantContext:
        if not tenant_id:
            raise UnknownTenantError("tenant_id must be a non-empty string")
        key = tenant_id.lower().strip()
        if key not in self._REGISTRY:
            raise UnknownTenantError(
                f"Unknown tenant '{tenant_id}'; "
                f"known tenants: {sorted(self._REGISTRY)}"
            )
        return self._REGISTRY[key]

    def known_tenants(self) -> list[str]:
        return sorted(self._REGISTRY)
