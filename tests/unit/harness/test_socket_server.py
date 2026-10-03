"""Harness against a real local HTTP server over TCP (no transport mocking).

Covers behaviour only a socket shows: read timeouts between chunks, the
server observing the client disconnect when a turn is cancelled, and
chunked transfer encoding split at arbitrary points.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import replace

import pytest

from src.harness.config import PRESETS
from src.harness.errors import ProviderTimeoutError
from src.harness.registry import build_provider
from src.harness.session import ChatSession
from src.harness.types import TextDelta

Handler = Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]]


@asynccontextmanager
async def serve(handler: Handler) -> AsyncIterator[str]:
    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}/v1"
    finally:
        server.close()
        await server.wait_closed()


async def _read_request(reader: asyncio.StreamReader) -> dict[str, object]:
    head = await reader.readuntil(b"\r\n\r\n")
    length = 0
    for line in head.decode().split("\r\n"):
        if line.lower().startswith("content-length:"):
            length = int(line.split(":", 1)[1])
    body = await reader.readexactly(length) if length else b""
    return json.loads(body) if body else {}


def _chunk(writer: asyncio.StreamWriter, data: str) -> None:
    raw = data.encode()
    writer.write(f"{len(raw):x}\r\n".encode() + raw + b"\r\n")


def _frame(text: str) -> str:
    return "data: " + json.dumps({"choices": [{"index": 0, "delta": {"content": text}}]}) + "\n\n"


HEAD = b"HTTP/1.1 200 OK\r\ncontent-type: text/event-stream\r\ntransfer-encoding: chunked\r\n\r\n"


async def test_chunked_stream_split_mid_frame() -> None:
    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await _read_request(reader)
        writer.write(HEAD)
        body = _frame("Hello ") + ": keepalive\n\n" + _frame("socket") + "data: [DONE]\n\n"
        for i in range(0, len(body), 7):
            _chunk(writer, body[i : i + 7])
            await writer.drain()
        writer.write(b"0\r\n\r\n")
        await writer.drain()
        writer.close()

    async with serve(handler) as url:
        profile = replace(PRESETS["openai-compatible"], base_url=url, model="m")
        async with build_provider(profile) as provider:
            session = ChatSession(provider)
            text = "".join(
                [e.text async for e in session.stream_turn("hi") if isinstance(e, TextDelta)]
            )
    assert text == "Hello socket"


async def test_read_timeout_mid_stream() -> None:
    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await _read_request(reader)
        writer.write(HEAD)
        _chunk(writer, _frame("first"))
        await writer.drain()
        await asyncio.sleep(1.5)  # stall longer than the read timeout
        writer.close()

    async with serve(handler) as url:
        profile = replace(
            PRESETS["openai-compatible"], base_url=url, model="m", read_timeout=0.3, max_retries=0
        )
        async with build_provider(profile) as provider:
            seen = []
            request = ChatSession(provider)._request()  # noqa: SLF001

            async def consume() -> None:
                async for e in provider.stream_chat(request):
                    seen.append(e)

            with pytest.raises(ProviderTimeoutError, match="mid-stream"):
                await consume()
    assert seen == [TextDelta("first")]


async def test_cancel_disconnects_from_server() -> None:
    disconnected = asyncio.Event()

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await _read_request(reader)
        writer.write(HEAD)
        try:
            for i in range(1000):
                _chunk(writer, _frame(f"{i} "))
                await writer.drain()
                await asyncio.sleep(0.01)
        except (ConnectionResetError, BrokenPipeError):
            disconnected.set()
            return
        finally:
            if reader.at_eof():
                disconnected.set()
        writer.close()

    async with serve(handler) as url:
        profile = replace(PRESETS["openai-compatible"], base_url=url, model="m")
        async with build_provider(profile) as provider:
            session = ChatSession(provider)
            got: list[object] = []

            async def consume() -> None:
                async for e in session.stream_turn("hi"):
                    got.append(e)

            task = asyncio.create_task(consume())
            while len(got) < 3:
                await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            await asyncio.wait_for(disconnected.wait(), timeout=3)
    assert len(got) < 1000
