from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from src.harness.config import PRESETS
from src.harness.errors import ProviderConnectionError, ProviderHTTPError
from src.harness.session import ChatSession
from src.harness.types import TextDelta, ToolCall

from .fakes import Reply, make_provider, openai_chunk, sse

PROFILE = replace(PRESETS["ollama"], model="m", max_retries=0)


async def _drain(session: ChatSession, text: str) -> list[object]:
    return [e async for e in session.stream_turn(text)]


async def test_successful_turn_records_history_and_usage() -> None:
    chunks = sse(
        openai_chunk("Hello"),
        openai_chunk(finish="stop"),
        {"choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 1}},
    )
    provider, transport, _ = make_provider(PROFILE, [Reply(chunks=chunks), Reply(chunks=chunks)])
    session = ChatSession(provider, system_prompt="sys")
    await _drain(session, "hi")
    assert [(m.role, m.content) for m in session.history] == [
        ("user", "hi"),
        ("assistant", "Hello"),
    ]
    assert session.total_usage.total_tokens == 6
    await _drain(session, "again")
    sent = transport.payload()["messages"]
    assert [m["role"] for m in sent] == ["system", "user", "assistant", "user"]
    assert session.total_usage.total_tokens == 12


async def test_failure_before_output_removes_user_message() -> None:
    provider, _, _ = make_provider(PROFILE, [Reply(status=500, chunks=["x"])])
    session = ChatSession(provider)
    with pytest.raises(ProviderHTTPError):
        await _drain(session, "hi")
    assert session.history == []


async def test_failure_after_partial_output_keeps_partial() -> None:
    chunks = sse(openai_chunk("par"), openai_chunk("tial"))
    provider, _, _ = make_provider(PROFILE, [Reply(chunks=chunks, fail_after=1)])
    session = ChatSession(provider)
    with pytest.raises(ProviderConnectionError):
        await _drain(session, "hi")
    assert [(m.role, m.content) for m in session.history] == [("user", "hi"), ("assistant", "par")]
    assert session.last_result is not None
    assert session.last_result.finish_reason == "cancelled_or_failed"


async def test_task_cancellation_closes_stream_and_keeps_partial() -> None:
    chunks = sse(*[openai_chunk(f"t{i} ") for i in range(100)])
    provider, transport, _ = make_provider(PROFILE, [Reply(chunks=chunks, delay=0.01)])
    session = ChatSession(provider)
    got: list[object] = []

    async def consume() -> None:
        async for e in session.stream_turn("hi"):
            got.append(e)

    task = asyncio.create_task(consume())
    while len(got) < 3:
        await asyncio.sleep(0.005)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert transport.closed.is_set()
    assert session.history[-1].role == "assistant"
    assert session.history[-1].content.startswith("t0 t1 t2")
    assert len(got) < 100


async def test_tool_calls_are_assembled() -> None:
    chunks = sse(
        openai_chunk(
            tool_calls=[{"index": 0, "id": "c1", "function": {"name": "f", "arguments": "{"}}]
        ),
        openai_chunk(
            tool_calls=[{"index": 1, "id": "c2", "function": {"name": "g", "arguments": ""}}]
        ),
        openai_chunk(tool_calls=[{"index": 0, "function": {"arguments": "}"}}]),
        openai_chunk(finish="tool_calls"),
    )
    provider, _, _ = make_provider(PROFILE, [Reply(chunks=chunks)])
    session = ChatSession(provider)
    events = await _drain(session, "go")
    assert not any(isinstance(e, TextDelta) for e in events)
    assert session.last_result is not None
    assert session.last_result.tool_calls == (ToolCall("c1", "f", "{}"), ToolCall("c2", "g", ""))
    assert session.history[-1].tool_calls == session.last_result.tool_calls


async def test_reset() -> None:
    provider, _, _ = make_provider(PROFILE, [Reply(chunks=sse(openai_chunk("x")))])
    session = ChatSession(provider)
    await _drain(session, "hi")
    session.reset()
    assert session.history == []
    assert session.last_result is None
