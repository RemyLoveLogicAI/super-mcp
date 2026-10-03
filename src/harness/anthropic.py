"""Native Anthropic Messages API streaming (``POST /v1/messages``)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

from src.harness.base import BaseProvider
from src.harness.errors import (
    AuthenticationError,
    BadResponseError,
    HarnessError,
    ProviderHTTPError,
    RateLimitError,
)
from src.harness.types import (
    ChatMessage,
    ChatRequest,
    Finish,
    HealthReport,
    StreamEvent,
    TextDelta,
    ToolCallDelta,
    Usage,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator

logger = structlog.get_logger(__name__)

_STOP_MAP = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
}
_DEFAULT_MAX_TOKENS = 4096


class AnthropicProvider(BaseProvider):
    """Anthropic Messages API with server-sent events."""

    def _auth_headers(self) -> dict[str, str]:
        headers = {"anthropic-version": self.profile.anthropic_version}
        if self._api_key is not None:
            headers["x-api-key"] = self._api_key.reveal()
        return headers

    def build_payload(self, request: ChatRequest) -> dict[str, Any]:
        system = "\n\n".join(
            m.content for m in request.messages if m.role == "system" and m.content
        )
        payload: dict[str, Any] = {
            "model": self._require_model(),
            "max_tokens": request.max_tokens
            or self.profile.default_max_tokens
            or _DEFAULT_MAX_TOKENS,
            "messages": _to_anthropic_messages(request.messages),
            "stream": True,
        }
        if system:
            payload["system"] = system
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.tools:
            payload["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in request.tools
            ]
        if request.stop:
            payload["stop_sequences"] = list(request.stop)
        return payload

    async def stream_chat(self, request: ChatRequest) -> AsyncGenerator[StreamEvent, None]:
        payload = self.build_payload(request)
        async with self._open_stream("messages", payload) as response:
            async for event in self._parse(response):
                yield event

    async def _parse(self, response: Any) -> AsyncIterator[StreamEvent]:
        stop_reason: str | None = None
        saw_stop = False
        valid = 0
        tool_index_for_block: dict[int, int] = {}
        async for sse in self._sse(response):
            try:
                data = json.loads(sse.data)
            except ValueError:
                await logger.adebug("sse_non_json_skipped", provider=self.name, size=len(sse.data))
                continue
            if not isinstance(data, dict):
                continue
            etype = data.get("type") or sse.event
            if etype == "error":
                raise self._stream_error(data)
            valid += 1
            if etype == "message_start":
                usage = (data.get("message") or {}).get("usage") or {}
                yield Usage(
                    input_tokens=_input_tokens(usage),
                    output_tokens=int(usage.get("output_tokens") or 0),
                )
            elif etype == "content_block_start":
                block = data.get("content_block") or {}
                if block.get("type") == "tool_use":
                    idx = len(tool_index_for_block)
                    tool_index_for_block[int(data.get("index", 0))] = idx
                    yield ToolCallDelta(index=idx, id=block.get("id"), name=block.get("name"))
                elif block.get("type") == "text" and block.get("text"):
                    yield TextDelta(str(block["text"]))
            elif etype == "content_block_delta":
                delta = data.get("delta") or {}
                dtype = delta.get("type")
                if dtype == "text_delta" and delta.get("text"):
                    yield TextDelta(str(delta["text"]))
                elif dtype == "input_json_delta":
                    block_idx = int(data.get("index", 0))
                    if block_idx in tool_index_for_block:
                        yield ToolCallDelta(
                            index=tool_index_for_block[block_idx],
                            arguments=str(delta.get("partial_json") or ""),
                        )
                # thinking / signature deltas are not surfaced
            elif etype == "message_delta":
                delta = data.get("delta") or {}
                if delta.get("stop_reason"):
                    raw = str(delta["stop_reason"])
                    stop_reason = _STOP_MAP.get(raw, raw)
                usage = data.get("usage") or {}
                if usage:
                    yield Usage(
                        input_tokens=_input_tokens(usage),
                        output_tokens=int(usage.get("output_tokens") or 0),
                    )
            elif etype == "message_stop":
                saw_stop = True
                break
            # "ping" and unknown event types are ignored.
        if valid == 0:
            raise BadResponseError(
                f"{self.endpoint} returned no Anthropic stream events", provider=self.name
            )
        yield Finish(stop_reason or ("stop" if saw_stop else "incomplete"))

    def _stream_error(self, data: dict[str, Any]) -> HarnessError:
        err = data.get("error") or {}
        etype = err.get("type", "error") if isinstance(err, dict) else "error"
        msg = err.get("message", "") if isinstance(err, dict) else str(err)
        text = f"{etype} from {self.endpoint} mid-stream: {msg}"
        if etype == "rate_limit_error":
            return RateLimitError(text, provider=self.name)
        if etype in ("authentication_error", "permission_error"):
            return AuthenticationError(text, provider=self.name)
        if etype == "overloaded_error":
            return ProviderHTTPError(text, status_code=529, provider=self.name)
        if etype == "invalid_request_error":
            return ProviderHTTPError(text, status_code=400, provider=self.name)
        return ProviderHTTPError(text, status_code=500, provider=self.name)

    async def check_health(self) -> HealthReport:
        try:
            data, latency = await self._get_json("models?limit=1000")
        except HarnessError as err:
            return HealthReport(
                ok=False,
                provider=self.name,
                endpoint=self.endpoint,
                model=self.model,
                latency_ms=0.0,
                detail=str(err),
                error=err,
            )
        ids = [
            str(m.get("id"))
            for m in (data.get("data") or [] if isinstance(data, dict) else [])
            if isinstance(m, dict) and m.get("id")
        ]
        available: bool | None = None
        if self.model and ids:
            # Aliases such as "claude-sonnet-4-5" resolve to dated ids.
            available = any(i == self.model or i.startswith(self.model + "-") for i in ids)
        detail = f"{len(ids)} model(s) listed"
        if available is False:
            detail += f"; {self.model!r} not among them"
        return HealthReport(
            ok=available is not False,
            provider=self.name,
            endpoint=self.endpoint,
            model=self.model,
            latency_ms=latency,
            detail=detail,
            model_available=available,
            models=tuple(ids),
        )


def _input_tokens(usage: dict[str, Any]) -> int:
    return sum(
        int(usage.get(k) or 0)
        for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    )


def _to_anthropic_messages(messages: tuple[ChatMessage, ...]) -> list[dict[str, Any]]:
    """Convert neutral messages, merging consecutive same-role turns."""
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "system":
            continue
        blocks: list[dict[str, Any]]
        if m.role == "tool":
            role = "user"
            blocks = [
                {"type": "tool_result", "tool_use_id": m.tool_call_id or "", "content": m.content}
            ]
        elif m.role == "assistant":
            role = "assistant"
            blocks = [{"type": "text", "text": m.content}] if m.content else []
            for tc in m.tool_calls:
                try:
                    args = json.loads(tc.arguments) if tc.arguments.strip() else {}
                except ValueError:
                    args = {"_raw": tc.arguments}
                blocks.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": args})
        else:
            role = "user"
            blocks = [{"type": "text", "text": m.content}]
        if not blocks:
            continue
        if out and out[-1]["role"] == role:
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": role, "content": blocks})
    return out
