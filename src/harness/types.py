"""Provider-neutral request and stream-event types.

The harness speaks one vocabulary regardless of backend. Providers translate
it to and from their wire formats; the TUI and CLI only ever see these types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from src.harness.errors import HarnessError

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A complete tool call requested by the model."""

    id: str
    name: str
    arguments: str  # raw JSON text exactly as the model produced it


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One conversation turn."""

    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None  # set when role == "tool"
    name: str | None = None


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """A function the model may call. ``parameters`` is a JSON Schema object."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=lambda: {"type": "object"})


@dataclass(frozen=True, slots=True)
class ChatRequest:
    """Everything a provider needs to run one completion."""

    messages: tuple[ChatMessage, ...]
    temperature: float | None = None
    max_tokens: int | None = None
    tools: tuple[ToolSpec, ...] = ()
    stop: tuple[str, ...] = ()


# ── Stream events ───────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TextDelta:
    """A fragment of assistant text."""

    text: str


@dataclass(frozen=True, slots=True)
class ToolCallDelta:
    """A fragment of a tool call.

    ``index`` identifies the call within the turn; ``id`` and ``name`` are set
    on the first fragment of a call, ``arguments`` carries partial JSON text.
    """

    index: int
    id: str | None = None
    name: str | None = None
    arguments: str = ""


@dataclass(frozen=True, slots=True)
class Usage:
    """Token accounting reported by the provider."""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def merge(self, other: Usage) -> Usage:
        """Combine two partial reports, keeping the larger value per field.

        Anthropic reports input tokens at stream start and output tokens at the
        end; some servers repeat cumulative totals. Taking the max of each field
        is correct for both shapes.
        """
        return Usage(
            input_tokens=max(self.input_tokens, other.input_tokens),
            output_tokens=max(self.output_tokens, other.output_tokens),
        )


@dataclass(frozen=True, slots=True)
class Finish:
    """End of the stream. ``reason`` is normalised: stop, length, tool_calls, error, or
    the provider's own string when it has no mapping."""

    reason: str


StreamEvent = TextDelta | ToolCallDelta | Usage | Finish


@dataclass(frozen=True, slots=True)
class HealthReport:
    """Result of a provider health check."""

    ok: bool
    provider: str
    endpoint: str
    model: str
    latency_ms: float
    detail: str = ""
    model_available: bool | None = None  # None when the endpoint cannot tell
    models: tuple[str, ...] = ()
    error: HarnessError | None = None
