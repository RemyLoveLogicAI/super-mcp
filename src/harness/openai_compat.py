"""OpenAI Chat Completions streaming: OpenAI, Ollama /v1, LM Studio, vLLM, any compatible URL."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

from src.harness.base import BaseProvider, extract_error_message
from src.harness.errors import (
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

_FINISH_MAP = {"function_call": "tool_calls", "eos": "stop", "end_turn": "stop"}


class OpenAICompatibleProvider(BaseProvider):
    """``POST {base_url}/chat/completions`` with ``stream: true``."""

    def _auth_headers(self) -> dict[str, str]:
        if self._api_key is None:
            return {}
        return {"Authorization": f"Bearer {self._api_key.reveal()}"}

    def build_payload(self, request: ChatRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._require_model(),
            "messages": [_message_to_wire(m) for m in request.messages],
            "stream": True,
        }
        if self.profile.stream_usage:
            payload["stream_options"] = {"include_usage": True}
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        max_tokens = request.max_tokens or self.profile.default_max_tokens
        if max_tokens is not None:
            payload[self.profile.max_tokens_field] = max_tokens
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in request.tools
            ]
        if request.stop:
            payload["stop"] = list(request.stop)
        return payload

    async def stream_chat(self, request: ChatRequest) -> AsyncGenerator[StreamEvent, None]:
        payload = self.build_payload(request)
        try:
            async with self._open_stream("chat/completions", payload) as response:
                async for event in self._parse(response):
                    yield event
            return
        except ProviderHTTPError as err:
            # Older OpenAI-compatible servers reject ``stream_options``. Nothing has
            # been yielded yet (the error came from opening the stream), so retry once
            # without it; usage is then simply not reported.
            if not (
                err.status_code in (400, 422)
                and "stream_options" in payload
                and "stream_options" in (err.body_excerpt + str(err))
            ):
                raise
        await logger.ainfo("stream_options_unsupported", provider=self.name)
        payload.pop("stream_options")
        async with self._open_stream("chat/completions", payload) as response:
            async for event in self._parse(response):
                yield event

    async def _parse(self, response: Any) -> AsyncIterator[StreamEvent]:
        finish_reason: str | None = None
        saw_done = False
        valid_chunks = 0
        skipped = 0
        async for sse in self._sse(response):
            data = sse.data.strip()
            if not data:
                continue
            if data == "[DONE]":
                saw_done = True
                break
            try:
                chunk = json.loads(data)
            except ValueError:
                skipped += 1
                await logger.adebug("sse_non_json_skipped", provider=self.name, size=len(data))
                continue
            if not isinstance(chunk, dict):
                skipped += 1
                continue
            if "error" in chunk:
                raise self._stream_error(chunk)
            valid_chunks += 1
            usage = chunk.get("usage")
            if isinstance(usage, dict):
                yield Usage(
                    input_tokens=int(usage.get("prompt_tokens") or 0),
                    output_tokens=int(usage.get("completion_tokens") or 0),
                )
            for choice in chunk.get("choices") or ():
                if not isinstance(choice, dict) or choice.get("index", 0) != 0:
                    continue
                delta = choice.get("delta") or {}
                content = delta.get("content")
                if isinstance(content, str) and content:
                    yield TextDelta(content)
                for tc in delta.get("tool_calls") or ():
                    if not isinstance(tc, dict):
                        continue
                    fn = tc.get("function") or {}
                    yield ToolCallDelta(
                        index=int(tc.get("index", 0)),
                        id=tc.get("id"),
                        name=fn.get("name"),
                        arguments=fn.get("arguments") or "",
                    )
                if choice.get("finish_reason"):
                    raw = str(choice["finish_reason"])
                    finish_reason = _FINISH_MAP.get(raw, raw)
        if valid_chunks == 0 and not saw_done:
            raise BadResponseError(
                f"{self.endpoint} returned no parseable stream chunks ({skipped} skipped); "
                "is this an OpenAI-compatible endpoint?",
                provider=self.name,
            )
        yield Finish(finish_reason or ("stop" if saw_done else "incomplete"))

    def _stream_error(self, chunk: dict[str, Any]) -> HarnessError:
        message = extract_error_message(json.dumps(chunk)) or "stream error"
        err = chunk.get("error")
        code = err.get("code") if isinstance(err, dict) else None
        text = f"error event from {self.endpoint} mid-stream: {message}"
        if code in (429, "429", "rate_limit_exceeded"):
            return RateLimitError(text, provider=self.name)
        status = code if isinstance(code, int) and 400 <= code < 600 else 502
        return ProviderHTTPError(text, status_code=status, provider=self.name)

    async def check_health(self) -> HealthReport:
        try:
            data, latency = await self._get_json("models")
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
        available = (self.model in ids) if (self.model and ids) else None
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


def _message_to_wire(message: ChatMessage) -> dict[str, Any]:
    wire: dict[str, Any] = {"role": message.role}
    if message.role == "assistant" and message.tool_calls:
        wire["content"] = message.content or None
        wire["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": tc.arguments},
            }
            for tc in message.tool_calls
        ]
    else:
        wire["content"] = message.content
    if message.role == "tool":
        wire["tool_call_id"] = message.tool_call_id
    if message.name:
        wire["name"] = message.name
    return wire
