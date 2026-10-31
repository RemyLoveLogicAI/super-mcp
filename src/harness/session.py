"""Conversation state on top of a provider.

``ChatSession.stream_turn`` is what the TUI and CLI drive: it appends the
user message, streams events through unchanged, assembles tool calls, and
records the assistant turn and token usage. History stays consistent when a
turn is cancelled or fails part-way.
"""

from __future__ import annotations

from contextlib import aclosing
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.harness.types import (
    ChatMessage,
    ChatRequest,
    Finish,
    StreamEvent,
    TextDelta,
    ToolCall,
    ToolCallDelta,
    ToolSpec,
    Usage,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from src.harness.base import BaseProvider


@dataclass(slots=True)
class _PartialCall:
    id: str = ""
    name: str = ""
    arguments: list[str] = field(default_factory=list)


class ToolCallAccumulator:
    """Folds :class:`ToolCallDelta` fragments into complete :class:`ToolCall` objects."""

    def __init__(self) -> None:
        self._calls: dict[int, _PartialCall] = {}

    def add(self, delta: ToolCallDelta) -> None:
        call = self._calls.setdefault(delta.index, _PartialCall())
        if delta.id:
            call.id = delta.id
        if delta.name:
            call.name = call.name or delta.name
        if delta.arguments:
            call.arguments.append(delta.arguments)

    def calls(self) -> tuple[ToolCall, ...]:
        return tuple(
            ToolCall(id=c.id or f"call_{i}", name=c.name, arguments="".join(c.arguments))
            for i, c in sorted(self._calls.items())
        )


@dataclass(frozen=True, slots=True)
class TurnResult:
    text: str
    tool_calls: tuple[ToolCall, ...]
    usage: Usage
    finish_reason: str


class ChatSession:
    """Multi-turn chat with one provider."""

    def __init__(
        self,
        provider: BaseProvider,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: tuple[ToolSpec, ...] = (),
    ) -> None:
        self.provider = provider
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tools = tools
        self.history: list[ChatMessage] = []
        self.total_usage = Usage()
        self.last_result: TurnResult | None = None

    def reset(self) -> None:
        self.history.clear()
        self.last_result = None

    def _request(self) -> ChatRequest:
        messages: list[ChatMessage] = []
        if self.system_prompt:
            messages.append(ChatMessage(role="system", content=self.system_prompt))
        messages.extend(self.history)
        return ChatRequest(
            messages=tuple(messages),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tools=self.tools,
        )

    async def stream_turn(self, user_text: str) -> AsyncIterator[StreamEvent]:
        """Send ``user_text`` and yield the provider's events as they arrive.

        On success the assistant turn is appended to history and
        :attr:`last_result` is set. If the turn fails or is cancelled before any
        output, the user message is removed so a retry does not duplicate it;
        after partial output, the partial assistant text is kept so the next
        turn sees what the user saw.
        """
        self.history.append(ChatMessage(role="user", content=user_text))
        text: list[str] = []
        tools = ToolCallAccumulator()
        usage = Usage()
        finish = "incomplete"
        completed = False
        try:
            async with aclosing(self.provider.stream_chat(self._request())) as stream:
                async for event in stream:
                    if isinstance(event, TextDelta):
                        text.append(event.text)
                    elif isinstance(event, ToolCallDelta):
                        tools.add(event)
                    elif isinstance(event, Usage):
                        usage = usage.merge(event)
                    elif isinstance(event, Finish):
                        finish = event.reason
                    yield event
            completed = True
        finally:
            body = "".join(text)
            calls = tools.calls()
            if completed or body or calls:
                self.history.append(ChatMessage(role="assistant", content=body, tool_calls=calls))
            else:
                self.history.pop()
            self.total_usage = Usage(
                input_tokens=self.total_usage.input_tokens + usage.input_tokens,
                output_tokens=self.total_usage.output_tokens + usage.output_tokens,
            )
            self.last_result = TurnResult(
                text=body,
                tool_calls=calls,
                usage=usage,
                finish_reason=finish if completed else "cancelled_or_failed",
            )
