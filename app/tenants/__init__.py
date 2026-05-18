"""
Tenant context resolution package.

Provides the TenantContextManager, which maps a raw tenant identifier from
an incoming request to a structured TenantContext object carrying the
tenant's policy scope, display name, and jurisdiction. The workflow engine
calls the manager as its first step, before policy evaluation.
"""
