"""Provider factory."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.harness.anthropic import AnthropicProvider
from src.harness.openai_compat import OpenAICompatibleProvider

if TYPE_CHECKING:
    from src.harness.base import BaseProvider
    from src.harness.config import ProviderProfile


def build_provider(profile: ProviderProfile, **kwargs: Any) -> BaseProvider:
    """Instantiate the provider class for ``profile.kind``.

    ``kwargs`` are forwarded to :class:`BaseProvider` (``api_key``,
    ``transport``, ``retry``, ``sleep``) and exist for embedding and tests.
    """
    if profile.kind == "anthropic":
        return AnthropicProvider(profile, **kwargs)
    return OpenAICompatibleProvider(profile, **kwargs)
