from __future__ import annotations

from dataclasses import replace

import pytest

from src.harness.config import PRESETS
from src.harness.errors import AuthenticationError, ProviderHTTPError, RateLimitError
from src.harness.types import (
    ChatMessage,
    ChatRequest,
    Finish,
    TextDelta,
    ToolCall,
    ToolCallDelta,
    ToolSpec,
    Usage,
)

from .fakes import Reply, anthropic_sse, make_provider

PROFILE = replace(PRESETS["anthropic"], model="claude-test")
REQ = ChatRequest(
    messages=(
        ChatMessage(role="system", content="Be brief."),
        ChatMessage(role="user", content="hi"),
    )
)

RECORDED = anthropic_sse(
    {
        "type": "message_start",
        "message": {"id": "msg_1", "usage": {"input_tokens": 12, "output_tokens": 1}},
    },
    {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
    {"type": "ping"},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hi"}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "!"}},
    {"type": "content_block_stop", "index": 0},
    {
        "type": "content_block_start",
        "index": 1,
        "content_block": {"type": "tool_use", "id": "toolu_1", "name": "lookup", "input": {}},
    },
    {
        "type": "content_block_delta",
        "index": 1,
        "delta": {"type": "input_json_delta", "partial_json": '{"q":'},
    },
    {
        "type": "content_block_delta",
        "index": 1,
        "delta": {"type": "input_json_delta", "partial_json": '"x"}'},
    },
    {"type": "content_block_stop", "index": 1},
    {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"output_tokens": 9}},
    {"type": "message_stop"},
)


async def _collect(provider, request=REQ):  # type: ignore[no-untyped-def]
    return [e async for e in provider.stream_chat(request)]


async def test_recorded_stream_maps_to_neutral_events() -> None:
    provider, transport, _ = make_provider(PROFILE, [Reply(chunks=RECORDED)], key="sk-ant-1")
    events = await _collect(provider)
    assert events == [
        Usage(12, 1),
        TextDelta("Hi"),
        TextDelta("!"),
        ToolCallDelta(0, "toolu_1", "lookup", ""),
        ToolCallDelta(0, None, None, '{"q":'),
        ToolCallDelta(0, None, None, '"x"}'),
        Usage(0, 9),
        Finish("tool_calls"),
    ]
    req = transport.requests[0]
    assert req.url == "https://api.anthropic.com/v1/messages"
    assert req.headers["x-api-key"] == "sk-ant-1"
    assert req.headers["anthropic-version"] == "2023-06-01"
    assert "authorization" not in req.headers
    body = transport.payload()
    assert body["system"] == "Be brief."
    assert body["max_tokens"] == 4096
    assert body["stream"] is True
    assert body["messages"] == [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]


async def test_tool_history_conversion_and_merging() -> None:
    provider, transport, _ = make_provider(PROFILE, [Reply(chunks=RECORDED)], key="k")
    request = ChatRequest(
        messages=(
            ChatMessage(role="user", content="q"),
            ChatMessage(
                role="assistant",
                content="checking",
                tool_calls=(
                    ToolCall("t1", "a", '{"x":1}'),
                    ToolCall("t2", "b", ""),
                ),
            ),
            ChatMessage(role="tool", content="r1", tool_call_id="t1"),
            ChatMessage(role="tool", content="r2", tool_call_id="t2"),
        ),
        tools=(ToolSpec("a", "A", {"type": "object"}),),
        stop=("END",),
        max_tokens=100,
    )
    await _collect(provider, request)
    body = transport.payload()
    assert body["tools"] == [{"name": "a", "description": "A", "input_schema": {"type": "object"}}]
    assert body["stop_sequences"] == ["END"]
    assert body["max_tokens"] == 100
    msgs = body["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[1]["content"][1] == {"type": "tool_use", "id": "t1", "name": "a", "input": {"x": 1}}
    assert msgs[1]["content"][2]["input"] == {}
    assert [b["tool_use_id"] for b in msgs[2]["content"]] == ["t1", "t2"]


@pytest.mark.parametrize(
    ("etype", "exc_type"),
    [
        ("overloaded_error", ProviderHTTPError),
        ("rate_limit_error", RateLimitError),
        ("authentication_error", AuthenticationError),
        ("api_error", ProviderHTTPError),
    ],
)
async def test_error_events(etype: str, exc_type: type) -> None:
    chunks = anthropic_sse(
        {"type": "message_start", "message": {"usage": {"input_tokens": 1}}},
        {"type": "error", "error": {"type": etype, "message": "boom"}},
    )
    provider, _, _ = make_provider(PROFILE, [Reply(chunks=chunks)], key="k")
    with pytest.raises(exc_type, match="boom"):
        await _collect(provider)


async def test_529_overloaded_status_is_retried() -> None:
    provider, transport, sleeps = make_provider(
        PROFILE,
        [
            Reply(status=529, chunks=['{"type":"error","error":{"type":"overloaded_error"}}']),
            Reply(chunks=RECORDED),
        ],
        key="k",
    )
    events = await _collect(provider)
    assert events[-1] == Finish("tool_calls")
    assert len(transport.requests) == 2
    assert len(sleeps.calls) == 1


async def test_health_matches_alias_prefix() -> None:
    body = '{"data":[{"id":"claude-sonnet-4-5-20250929"}]}'
    provider, transport, _ = make_provider(
        replace(PROFILE, model="claude-sonnet-4-5"), [Reply(chunks=[body])], key="k"
    )
    report = await provider.check_health()
    assert report.ok
    assert report.model_available
    assert transport.requests[0].headers["x-api-key"] == "k"
