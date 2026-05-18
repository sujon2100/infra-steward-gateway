"""Tests for the TenantContextManager."""

import pytest

from app.tenants.context_manager import TenantContextManager, UnknownTenantError


def test_resolve_known_tenant_returns_context() -> None:
    mgr = TenantContextManager()
    ctx = mgr.resolve("bank_alpha")
    assert ctx.tenant_id == "bank_alpha"
    assert ctx.display_name == "Bank Alpha"
    assert ctx.policy_scope == "bank_alpha_policy"
    assert ctx.jurisdiction == "EU"


def test_resolve_is_case_insensitive() -> None:
    mgr = TenantContextManager()
    assert mgr.resolve("BANK_NEPTUNE").jurisdiction == "APAC"


def test_resolve_unknown_tenant_raises() -> None:
    mgr = TenantContextManager()
    with pytest.raises(UnknownTenantError):
        mgr.resolve("bank_unknown")


def test_resolve_empty_tenant_raises() -> None:
    mgr = TenantContextManager()
    with pytest.raises(UnknownTenantError):
        mgr.resolve("")


def test_known_tenants_lists_all() -> None:
    mgr = TenantContextManager()
    assert mgr.known_tenants() == ["bank_alpha", "bank_beta", "bank_mars", "bank_neptune"]
