"""Test fixtures: scripted HTTP endpoints for the harness.

``ScriptedTransport`` is an ``httpx`` transport that answers from a queue of
canned responses and records every request, so tests can assert on exact
headers and payloads and on how many attempts were made. Streaming bodies
are delivered in caller-chosen fragments to exercise the incremental parser.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx

from src.harness.config import ProviderProfile, Secret
from src.harness.registry import build_provider

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterable


@dataclass
class Reply:
    status: int = 200
    chunks: Iterable[str | bytes] = ()
    headers: dict[str, str] = field(default_factory=dict)
    delay: float = 0.0  # seconds between chunks
    raise_exc: Exception | None = None  # raised instead of answering
    fail_after: int | None = None  # raise ReadError after N chunks


class _Body(httpx.AsyncByteStream):
    def __init__(self, reply: Reply, closed: asyncio.Event) -> None:
        self._reply = reply
        self._closed = closed

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for i, chunk in enumerate(self._reply.chunks):
            if self._reply.fail_after is not None and i >= self._reply.fail_after:
                raise httpx.ReadError("connection reset by peer")
            if self._reply.delay:
                await asyncio.sleep(self._reply.delay)
            yield chunk.encode() if isinstance(chunk, str) else chunk

    async def aclose(self) -> None:
        self._closed.set()


class ScriptedTransport(httpx.AsyncBaseTransport):
    def __init__(self, replies: list[Reply]) -> None:
        self.replies = list(replies)
        self.requests: list[httpx.Request] = []
        self.closed = asyncio.Event()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        await request.aread()
        self.requests.append(request)
        if not self.replies:
            raise AssertionError("unexpected extra request")
        reply = self.replies.pop(0)
        if reply.raise_exc is not None:
            raise reply.raise_exc
        return httpx.Response(
            reply.status,
            headers={"content-type": "text/event-stream", **reply.headers},
            stream=_Body(reply, self.closed),
            request=request,
        )

    def payload(self, i: int = -1) -> dict[str, Any]:
        return json.loads(self.requests[i].content)


class SleepRecorder:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.calls.append(delay)


def sse(*events: dict[str, Any] | str, done: bool = True) -> list[str]:
    """OpenAI-style SSE frames."""
    frames = [f"data: {e if isinstance(e, str) else json.dumps(e)}\n\n" for e in events]
    if done:
        frames.append("data: [DONE]\n\n")
    return frames


def anthropic_sse(*events: dict[str, Any]) -> list[str]:
    return [f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events]


def openai_chunk(
    content: str | None = None, finish: str | None = None, **delta: Any
) -> dict[str, Any]:
    d: dict[str, Any] = dict(delta)
    if content is not None:
        d["content"] = content
    return {"choices": [{"index": 0, "delta": d, "finish_reason": finish}]}


def make_provider(
    profile: ProviderProfile,
    replies: list[Reply],
    *,
    key: str | None = None,
    sleep: Callable[[float], Any] | None = None,
) -> tuple[Any, ScriptedTransport, SleepRecorder]:
    transport = ScriptedTransport(replies)
    recorder = SleepRecorder()
    provider = build_provider(
        profile,
        api_key=Secret(key) if key else None,
        transport=transport,
        sleep=sleep or recorder,
    )
    return provider, transport, recorder
