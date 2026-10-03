from __future__ import annotations

import pytest

from src.harness.sse import SSEDecoder, SSEEvent, iter_sse


def _decode(chunks: list[str]) -> list[SSEEvent]:
    d = SSEDecoder()
    out: list[SSEEvent] = []
    for c in chunks:
        out.extend(d.feed(c))
    out.extend(d.flush())
    return out


def test_basic_events_and_done_passthrough() -> None:
    events = _decode(['data: {"a":1}\n\n', "data: [DONE]\n\n"])
    assert [e.data for e in events] == ['{"a":1}', "[DONE]"]


@pytest.mark.parametrize("eol", ["\n", "\r\n", "\r"])
def test_line_endings(eol: str) -> None:
    raw = f"event: delta{eol}data: one{eol}{eol}data: two{eol}{eol}"
    events = _decode([raw])
    assert [(e.event, e.data) for e in events] == [("delta", "one"), ("message", "two")]


def test_byte_by_byte_feeding_with_crlf() -> None:
    raw = ": keep-alive\r\n\r\ndata: hel\r\ndata: lo\r\n\r\ndata: x\r\n\r\n"
    events = _decode(list(raw))
    assert [e.data for e in events] == ["hel\nlo", "x"]


def test_crlf_split_across_chunks_does_not_create_blank_line() -> None:
    events = _decode(["data: a\r", "\ndata: b\r\n\r\n"])
    assert [e.data for e in events] == ["a\nb"]


def test_comments_and_blank_keepalives_are_skipped() -> None:
    events = _decode([": ping\n\n", "\n\n", ":\n", "data: real\n\n"])
    assert [e.data for e in events] == ["real"]


def test_field_without_space_and_unknown_fields() -> None:
    events = _decode(["data:nospace\nretry: 100\nfoo: bar\nid: 7\n\n"])
    assert events == [SSEEvent(data="nospace", event="message", id="7")]


def test_unterminated_final_event_is_flushed() -> None:
    events = _decode(["data: first\n\n", "data: last-without-blank-line"])
    assert [e.data for e in events] == ["first", "last-without-blank-line"]


def test_event_type_resets_between_events() -> None:
    events = _decode(["event: a\ndata: 1\n\ndata: 2\n\n"])
    assert [e.event for e in events] == ["a", "message"]


async def test_iter_sse_async() -> None:
    async def gen():  # type: ignore[no-untyped-def]
        for c in ["da", "ta: x\n", "\n"]:
            yield c

    assert [e.data async for e in iter_sse(gen())] == ["x"]
