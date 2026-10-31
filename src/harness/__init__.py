"""Provider harness: one streaming chat interface over OpenAI-compatible and Anthropic APIs.

Layers: :mod:`config` (profiles, keys) → :mod:`base` (transport, retries,
typed errors) → :mod:`openai_compat` / :mod:`anthropic` (wire formats) →
:mod:`session` (conversation state). The CLI and the Textual TUI consume
:class:`ChatSession` and the neutral events in :mod:`types`.
"""

from src.harness.base import BaseProvider
from src.harness.config import (
    PRESETS,
    HarnessConfig,
    ProviderProfile,
    Secret,
    resolve_api_key,
    resolve_profile,
)
from src.harness.errors import (
    AuthenticationError,
    BadResponseError,
    ConfigError,
    HarnessError,
    ProviderConnectionError,
    ProviderHTTPError,
    ProviderTimeoutError,
    RateLimitError,
)
from src.harness.registry import build_provider
from src.harness.retry import RetryPolicy
from src.harness.session import ChatSession, ToolCallAccumulator, TurnResult
from src.harness.types import (
    ChatMessage,
    ChatRequest,
    Finish,
    HealthReport,
    StreamEvent,
    TextDelta,
    ToolCall,
    ToolCallDelta,
    ToolSpec,
    Usage,
)

__all__ = [
    "PRESETS",
    "AuthenticationError",
    "BadResponseError",
    "BaseProvider",
    "ChatMessage",
    "ChatRequest",
    "ChatSession",
    "ConfigError",
    "Finish",
    "HarnessConfig",
    "HarnessError",
    "HealthReport",
    "ProviderConnectionError",
    "ProviderHTTPError",
    "ProviderProfile",
    "ProviderTimeoutError",
    "RateLimitError",
    "RetryPolicy",
    "Secret",
    "StreamEvent",
    "TextDelta",
    "ToolCall",
    "ToolCallAccumulator",
    "ToolCallDelta",
    "ToolSpec",
    "TurnResult",
    "Usage",
    "build_provider",
    "resolve_api_key",
    "resolve_profile",
]
