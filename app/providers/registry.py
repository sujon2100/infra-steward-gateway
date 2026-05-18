"""
Provider registry for the InfraSteward gateway.

Holds the set of AI providers available to the workflow engine and looks them
up by name. The policy service returns a provider name per request; the engine
asks the registry for the corresponding provider instance.
"""

from __future__ import annotations

from app.providers.base import AbstractAIProvider


class ProviderNotRegisteredError(KeyError):
    """Raised when the engine asks for a provider that was never registered."""


class ProviderRegistry:
    def __init__(self, default_name: str | None = None) -> None:
        self._providers: dict[str, AbstractAIProvider] = {}
        self._default_name: str | None = default_name

    def register(self, name: str, provider: AbstractAIProvider) -> None:
        if not name:
            raise ValueError("Provider name must be a non-empty string")
        self._providers[name] = provider
        if self._default_name is None:
            self._default_name = name

    def get(self, name: str | None) -> AbstractAIProvider:
        lookup = name or self._default_name
        if lookup is None or lookup not in self._providers:
            raise ProviderNotRegisteredError(
                f"Provider '{lookup}' is not registered; "
                f"known providers: {sorted(self._providers)}"
            )
        return self._providers[lookup]

    def names(self) -> list[str]:
        return sorted(self._providers)

    @property
    def default_name(self) -> str | None:
        return self._default_name
