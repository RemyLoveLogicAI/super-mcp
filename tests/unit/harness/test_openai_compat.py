from __future__ import annotations

from dataclasses import replace

import httpx
import pytest

from src.harness.config import PRESETS
from src.harness.errors import (
    AuthenticationError,
    BadResponseError,
    ConfigError,
    ProviderConnectionError,
    ProviderHTTPError,
    ProviderTimeoutError,
    RateLimitError,
)
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

from .fakes import Reply, make_provider, openai_chunk, sse

OLLAMA = replace(PRESETS["ollama"], model="qwen2.5:0.5b")
OPENAI = replace(PRESETS["openai"], model="gpt-test")
REQ = ChatRequest(messages=(ChatMessage(role="user", content="hi"),))


async def _collect(provider, request=REQ):  # type: ignore[no-untyped-def]
    return [e async for e in provider.stream_chat(request)]


async def test_streams_text_usage_and_finish_in_order() -> None:
    chunks = sse(
        openai_chunk(role="assistant"),
        openai_chunk("Hel"),
        openai_chunk("lo"),
        openai_chunk(finish="stop"),
        {"choices": [], "usage": {"prompt_tokens": 7, "completion_tokens": 2}},
    )
    provider, transport, _ = make_provider(OLLAMA, [Reply(chunks=chunks)])
    events = await _collect(provider)
    assert events == [TextDelta("Hel"), TextDelta("lo"), Usage(7, 2), Finish("stop")]
    payload = transport.payload()
    assert payload["stream"] is True
    assert payload["stream_options"] == {"include_usage": True}
    assert payload["model"] == "qwen2.5:0.5b"
    assert transport.requests[0].url == "http://localhost:11434/v1/chat/completions"


async def test_no_authorization_header_without_key() -> None:
    provider, transport, _ = make_provider(OLLAMA, [Reply(chunks=sse(openai_chunk("x")))])
    await _collect(provider)
    assert "authorization" not in transport.requests[0].headers


async def test_ignores_openai_key_in_env_for_local_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-must-not-leak")
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY_FILE", raising=False)
    from src.harness.registry import build_provider

    from .fakes import ScriptedTransport

    transport = ScriptedTransport([Reply(chunks=sse(openai_chunk("x")))])
    provider = build_provider(OLLAMA, transport=transport)
    await _collect(provider)
    assert "authorization" not in transport.requests[0].headers


async def test_bearer_header_and_max_completion_tokens_for_openai() -> None:
    provider, transport, _ = make_provider(
        OPENAI, [Reply(chunks=sse(openai_chunk("x")))], key="sk-1"
    )
    await _collect(provider, ChatRequest(messages=REQ.messages, max_tokens=64, temperature=0.2))
    req = transport.requests[0]
    assert req.headers["authorization"] == "Bearer sk-1"
    body = transport.payload()
    assert body["max_completion_tokens"] == 64
    assert "max_tokens" not in body
    assert body["temperature"] == 0.2


async def test_keepalives_comments_and_malformed_lines_are_tolerated() -> None:
    chunks = [
        ": OPENROUTER PROCESSING\n\n",
        "\n",
        "data: {not json\n\n",
        'data: {"choices":[{"index":0,"delta":{"content":"ok"}}]}\n\n',
        "data: [DONE]\n\n",
    ]
    provider, _, _ = make_provider(OLLAMA, [Reply(chunks=chunks)])
    assert await _collect(provider) == [TextDelta("ok"), Finish("stop")]


async def test_fragmented_network_chunks() -> None:
    raw = "".join(sse(openai_chunk("héllo wörld"), openai_chunk(finish="length")))
    data = raw.encode()
    pieces = [data[i : i + 3] for i in range(0, len(data), 3)]  # splits UTF-8 sequences too
    provider, _, _ = make_provider(OLLAMA, [Reply(chunks=pieces)])
    events = await _collect(provider)
    assert "".join(e.text for e in events if isinstance(e, TextDelta)) == "héllo wörld"
    assert events[-1] == Finish("length")


async def test_tool_call_deltas_pass_through_and_tools_payload() -> None:
    chunks = sse(
        openai_chunk(
            tool_calls=[
                {
                    "index": 0,
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": ""},
                }
            ]
        ),
        openai_chunk(tool_calls=[{"index": 0, "function": {"arguments": '{"city":'}}]),
        openai_chunk(tool_calls=[{"index": 0, "function": {"arguments": '"Paris"}'}}]),
        openai_chunk(finish="tool_calls"),
    )
    provider, transport, _ = make_provider(OLLAMA, [Reply(chunks=chunks)])
    request = ChatRequest(
        messages=(
            ChatMessage(role="user", content="weather?"),
            ChatMessage(
                role="assistant",
                tool_calls=(ToolCall(id="c0", name="get_weather", arguments='{"city":"Rome"}'),),
            ),
            ChatMessage(role="tool", content="18C", tool_call_id="c0"),
        ),
        tools=(ToolSpec("get_weather", "Weather", {"type": "object"}),),
    )
    events = await _collect(provider, request)
    assert events[:3] == [
        ToolCallDelta(0, "call_1", "get_weather", ""),
        ToolCallDelta(0, None, None, '{"city":'),
        ToolCallDelta(0, None, None, '"Paris"}'),
    ]
    assert events[-1] == Finish("tool_calls")
    body = transport.payload()
    assert body["tools"][0]["function"]["name"] == "get_weather"
    assert body["messages"][1]["content"] is None
    assert body["messages"][1]["tool_calls"][0]["function"]["arguments"] == '{"city":"Rome"}'
    assert body["messages"][2] == {"role": "tool", "content": "18C", "tool_call_id": "c0"}


async def test_missing_done_and_finish_reports_incomplete() -> None:
    provider, _, _ = make_provider(OLLAMA, [Reply(chunks=sse(openai_chunk("par"), done=False))])
    assert await _collect(provider) == [TextDelta("par"), Finish("incomplete")]


async def test_non_openai_body_is_bad_response() -> None:
    provider, _, _ = make_provider(OLLAMA, [Reply(chunks=["<html>hello</html>"])])
    with pytest.raises(BadResponseError, match="no parseable"):
        await _collect(provider)


async def test_error_event_mid_stream_is_typed() -> None:
    chunks = sse(openai_chunk("a"), {"error": {"message": "overloaded", "code": 503}}, done=False)
    provider, _, _ = make_provider(OLLAMA, [Reply(chunks=chunks)])
    with pytest.raises(ProviderHTTPError, match="overloaded") as exc:
        await _collect(provider)
    assert exc.value.status_code == 503


@pytest.mark.parametrize(
    ("status", "exc_type"),
    [
        (401, AuthenticationError),
        (403, AuthenticationError),
        (400, ProviderHTTPError),
        (404, ProviderHTTPError),
        (422, ProviderHTTPError),
    ],
)
async def test_client_errors_are_typed_and_not_retried(status: int, exc_type: type) -> None:
    body = '{"error":{"message":"nope"}}'
    provider, transport, sleeps = make_provider(
        OPENAI, [Reply(status=status, chunks=[body])], key="sk-secret-value"
    )
    with pytest.raises(exc_type) as exc:
        await _collect(provider)
    assert len(transport.requests) == 1
    assert sleeps.calls == []
    assert "nope" in str(exc.value)
    assert "sk-secret-value" not in str(exc.value)


async def test_429_honours_retry_after_then_succeeds() -> None:
    provider, transport, sleeps = make_provider(
        OLLAMA,
        [
            Reply(status=429, chunks=['{"error":"slow down"}'], headers={"retry-after": "2"}),
            Reply(chunks=sse(openai_chunk("ok"))),
        ],
    )
    assert TextDelta("ok") in await _collect(provider)
    assert len(transport.requests) == 2
    assert sleeps.calls == [2.0]


async def test_5xx_retries_with_backoff_then_gives_up() -> None:
    profile = replace(OLLAMA, max_retries=2)
    provider, transport, sleeps = make_provider(
        profile, [Reply(status=503, chunks=["busy"]) for _ in range(3)]
    )
    with pytest.raises(ProviderHTTPError) as exc:
        await _collect(provider)
    assert exc.value.status_code == 503
    assert len(transport.requests) == 3
    assert len(sleeps.calls) == 2


async def test_rate_limit_exhaustion_raises_rate_limit_error() -> None:
    profile = replace(OLLAMA, max_retries=1)
    provider, _, _ = make_provider(profile, [Reply(status=429), Reply(status=429)])
    with pytest.raises(RateLimitError):
        await _collect(provider)


async def test_connect_errors_retry_and_map() -> None:
    profile = replace(OLLAMA, max_retries=1)
    provider, transport, sleeps = make_provider(
        profile,
        [Reply(raise_exc=httpx.ConnectError("refused")), Reply(raise_exc=httpx.ConnectError("x"))],
    )
    with pytest.raises(ProviderConnectionError):
        await _collect(provider)
    assert len(transport.requests) == 2
    assert len(sleeps.calls) == 1


async def test_connect_timeout_maps_to_timeout_error() -> None:
    profile = replace(OLLAMA, max_retries=0)
    provider, _, _ = make_provider(profile, [Reply(raise_exc=httpx.ConnectTimeout("t"))])
    with pytest.raises(ProviderTimeoutError):
        await _collect(provider)


async def test_mid_stream_disconnect_is_not_retried() -> None:
    chunks = sse(openai_chunk("a"), openai_chunk("b"), openai_chunk("c"))
    provider, transport, sleeps = make_provider(OLLAMA, [Reply(chunks=chunks, fail_after=1)])
    seen = []

    async def consume() -> None:
        async for e in provider.stream_chat(REQ):
            seen.append(e)

    with pytest.raises(ProviderConnectionError, match="interrupted"):
        await consume()
    assert seen == [TextDelta("a")]
    assert len(transport.requests) == 1
    assert sleeps.calls == []


async def test_closing_the_stream_early_closes_the_response() -> None:
    chunks = sse(*[openai_chunk(str(i)) for i in range(50)])
    provider, transport, _ = make_provider(OLLAMA, [Reply(chunks=chunks)])
    gen = provider.stream_chat(REQ)
    assert await gen.__anext__() == TextDelta("0")
    await gen.aclose()
    assert transport.closed.is_set()


async def test_model_required() -> None:
    provider, _, _ = make_provider(replace(OLLAMA, model=""), [])
    with pytest.raises(ConfigError, match="no model"):
        await _collect(provider)


async def test_health_check_reports_model_availability() -> None:
    body = '{"object":"list","data":[{"id":"qwen2.5:0.5b"},{"id":"llama3"}]}'
    provider, transport, _ = make_provider(OLLAMA, [Reply(chunks=[body])])
    report = await provider.check_health()
    assert report.ok
    assert report.model_available
    assert report.models == ("qwen2.5:0.5b", "llama3")
    assert transport.requests[0].url == "http://localhost:11434/v1/models"

    provider, _, _ = make_provider(replace(OLLAMA, model="missing"), [Reply(chunks=[body])])
    report = await provider.check_health()
    assert not report.ok
    assert report.model_available is False


async def test_health_check_never_raises() -> None:
    provider, _, _ = make_provider(OPENAI, [Reply(status=401, chunks=["{}"])], key="k")
    report = await provider.check_health()
    assert not report.ok
    assert isinstance(report.error, AuthenticationError)


async def test_server_rejecting_stream_options_is_retried_without_it() -> None:
    provider, transport, _ = make_provider(
        OLLAMA,
        [
            Reply(status=400, chunks=['{"error":{"message":"Unknown field: stream_options"}}']),
            Reply(chunks=sse(openai_chunk("ok"))),
        ],
    )
    assert await _collect(provider) == [TextDelta("ok"), Finish("stop")]
    assert "stream_options" in transport.payload(0)
    assert "stream_options" not in transport.payload(1)


async def test_other_400s_are_not_retried_without_stream_options() -> None:
    provider, transport, _ = make_provider(OLLAMA, [Reply(status=400, chunks=['{"error":"bad"}'])])
    with pytest.raises(ProviderHTTPError):
        await _collect(provider)
    assert len(transport.requests) == 1


async def test_key_echoed_by_server_is_redacted() -> None:
    body = '{"error":{"message":"Incorrect API key provided: sk-echo-123"}}'
    provider, _, _ = make_provider(OPENAI, [Reply(status=401, chunks=[body])], key="sk-echo-123")
    with pytest.raises(AuthenticationError) as exc:
        await _collect(provider)
    assert "sk-echo-123" not in str(exc.value)
    assert "[REDACTED]" in str(exc.value)
