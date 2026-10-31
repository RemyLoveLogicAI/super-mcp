"""The real Textual app driving a ChatSession, end to end through the widgets."""

from __future__ import annotations

from dataclasses import replace

from textual.widgets import RichLog

from src.harness.config import PRESETS
from src.harness.session import ChatSession
from src.tui.app import SuperMCPApp
from src.tui.components.status_bar import StatusBar

from .fakes import Reply, make_provider, openai_chunk, sse

PROFILE = replace(PRESETS["ollama"], model="tiny", max_retries=0)


def _log_text(app: SuperMCPApp) -> str:
    return "\n".join(line.text for line in app.query_one("#output-log", RichLog).lines)


async def _type(pilot, text: str) -> None:  # type: ignore[no-untyped-def]
    await pilot.press(*text)
    await pilot.press("enter")


async def test_streams_answer_into_output_and_status() -> None:
    chunks = sse(
        openai_chunk("Hi [bold]there[/bold]"),
        openai_chunk(finish="stop"),
        {"choices": [], "usage": {"prompt_tokens": 4, "completion_tokens": 3}},
    )
    provider, transport, _ = make_provider(PROFILE, [Reply(chunks=chunks)])
    app = SuperMCPApp(chat=ChatSession(provider))
    async with app.run_test() as pilot:
        await _type(pilot, "hello")
        await app.workers.wait_for_complete()
        await pilot.pause()
        text = _log_text(app)
        assert "tiny› Hi [bold]there[/bold]" in text  # model text is not markup
        status = app.query_one(StatusBar)
        assert status.mode == "COMMAND"
        assert "last 4→3" in status.health_text
        assert "session 7 tok" in status.health_text
        events = "\n".join(line.text for line in app.query_one("#event-log", RichLog).lines)
        assert "llm.request" in events
        assert "llm.completed" in events
    assert transport.payload()["messages"][-1] == {"role": "user", "content": "hello"}


async def test_escape_cancels_streaming_response() -> None:
    chunks = sse(*[openai_chunk(f"w{i} ") for i in range(400)])
    provider, transport, _ = make_provider(PROFILE, [Reply(chunks=chunks, delay=0.01)])
    session = ChatSession(provider)
    app = SuperMCPApp(chat=session)
    async with app.run_test() as pilot:
        await _type(pilot, "go")
        for _ in range(100):
            await pilot.pause(0.02)
            if app.query_one(StatusBar).mode == "STREAMING" and len(session.history) == 1:
                break
        await pilot.pause(0.1)
        assert app.chat_busy
        await pilot.press("escape")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert "[cancelled]" in _log_text(app)
        assert not app.chat_busy
        assert app.query_one(StatusBar).mode == "COMMAND"
        assert transport.closed.is_set()
        assert session.history[-1].role == "assistant"
        assert len(session.history[-1].content.split()) < 400


async def test_errors_are_shown_not_streamed_as_text() -> None:
    provider, _, _ = make_provider(
        PROFILE, [Reply(status=401, chunks=['{"error":{"message":"bad key"}}'])]
    )
    session = ChatSession(provider)
    app = SuperMCPApp(chat=session)
    async with app.run_test() as pilot:
        await _type(pilot, "hello")
        await app.workers.wait_for_complete()
        await pilot.pause()
        text = _log_text(app)
        assert "AuthenticationError" in text
        assert "bad key" in text
        assert session.history == []


async def test_chat_disabled_message_and_commands() -> None:
    app = SuperMCPApp(chat_unavailable="no API key configured")
    async with app.run_test() as pilot:
        await _type(pilot, "hello")
        await _type(pilot, "/cancel")
        await pilot.pause()
        text = _log_text(app)
        assert "Chat disabled: no API key configured" in text
        assert "Nothing is streaming." in text


async def test_ping_and_reset_commands() -> None:
    body = '{"data":[{"id":"tiny"}]}'
    provider, _, _ = make_provider(
        PROFILE, [Reply(chunks=sse(openai_chunk("x"))), Reply(chunks=[body])]
    )
    session = ChatSession(provider)
    app = SuperMCPApp(chat=session)
    async with app.run_test() as pilot:
        await _type(pilot, "hi")
        await app.workers.wait_for_complete()
        await _type(pilot, "/ping")
        await pilot.pause()
        await _type(pilot, "/reset")
        await pilot.pause()
        text = _log_text(app)
        assert "reachable" in text
        assert "Chat history cleared." in text
        assert session.history == []
