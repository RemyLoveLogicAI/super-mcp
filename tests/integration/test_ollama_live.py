"""Live integration tests against a real local OpenAI-compatible server.

Defaults target Ollama on ``http://localhost:11434/v1`` with model
``qwen2.5:0.5b``; override with ``SMCP_IT_ENDPOINT`` / ``SMCP_IT_MODEL``.
Every test is skipped (with the reason shown) when the endpoint is down or
the model is not pulled, so the suite stays green on machines without one::

    ollama pull qwen2.5:0.5b
    pytest -m integration -rs
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from src.harness.config import PRESETS
from src.harness.registry import build_provider
from src.harness.session import ChatSession
from src.harness.types import Finish, TextDelta, Usage

ENDPOINT = os.environ.get("SMCP_IT_ENDPOINT", "http://localhost:11434/v1")
MODEL = os.environ.get("SMCP_IT_MODEL", "qwen2.5:0.5b")
REPO = Path(__file__).resolve().parents[2]


def _endpoint_status() -> str | None:
    try:
        resp = httpx.get(f"{ENDPOINT}/models", timeout=3)
    except httpx.HTTPError as exc:
        return f"no server at {ENDPOINT} ({type(exc).__name__})"
    if resp.status_code != 200:
        return f"{ENDPOINT}/models returned {resp.status_code}"
    ids = [m.get("id") for m in resp.json().get("data", [])]
    if MODEL not in ids:
        return f"model {MODEL!r} not available at {ENDPOINT} (have: {ids})"
    return None


_SKIP = _endpoint_status()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(_SKIP is not None, reason=f"live endpoint unavailable: {_SKIP}"),
]

PROFILE = replace(
    PRESETS["openai-compatible"], name="live", base_url=ENDPOINT, model=MODEL, read_timeout=180
)


async def test_live_health() -> None:
    async with build_provider(PROFILE) as provider:
        report = await provider.check_health()
    assert report.ok
    assert report.model_available


async def test_live_stream_text_usage_and_multi_turn() -> None:
    async with build_provider(PROFILE) as provider:
        session = ChatSession(provider, temperature=0, max_tokens=16)
        events = [e async for e in session.stream_turn("Reply with exactly the word: pong")]
        text = "".join(e.text for e in events if isinstance(e, TextDelta))
        assert "pong" in text.lower()
        assert sum(isinstance(e, TextDelta) for e in events) >= 1
        usage = [e for e in events if isinstance(e, Usage)]
        assert usage
        assert usage[-1].input_tokens > 0
        assert usage[-1].output_tokens > 0
        assert isinstance(events[-1], Finish)
        assert events[-1].reason in ("stop", "length")

        events = [e async for e in session.stream_turn("Repeat your previous answer.")]
        assert len(session.history) == 4
        assert any(isinstance(e, TextDelta) for e in events)


async def test_live_cancellation_mid_stream() -> None:
    async with build_provider(PROFILE) as provider:
        session = ChatSession(provider, max_tokens=400)
        got: list[TextDelta] = []

        async def consume() -> None:
            async for e in session.stream_turn("Count from 1 to 300, one number per line."):
                if isinstance(e, TextDelta):
                    got.append(e)

        task = asyncio.create_task(consume())
        for _ in range(600):
            if len(got) >= 3:
                break
            await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert 3 <= len(got) < 400
        assert session.history[-1].role == "assistant"

        # The connection pool is still usable after a cancel.
        report = await provider.check_health()
        assert report.ok


async def test_live_bad_model_is_typed_404() -> None:
    from src.harness.errors import ProviderHTTPError

    async with build_provider(replace(PROFILE, model="no-such-model:0b")) as provider:
        session = ChatSession(provider)
        with pytest.raises(ProviderHTTPError) as exc:
            async for _ in session.stream_turn("hi"):
                pass
    assert exc.value.status_code == 404


def test_live_cli_plain_mode_end_to_end() -> None:
    env = {k: v for k, v in os.environ.items() if not k.endswith("API_KEY")}
    proc = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "src.cli",
            "-p",
            "openai-compatible",
            "-e",
            ENDPOINT,
            "-m",
            MODEL,
            "start",
            "--no-tui",
            "--show-usage",
            "--max-tokens",
            "8",
            "Say the word: ok",
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip()
    assert "[usage] in=" in proc.stderr


def test_live_cli_ping() -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "src.cli", "-e", ENDPOINT, "-m", MODEL, "ping"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "reachable" in proc.stdout


async def test_live_tui_chat() -> None:
    from textual.widgets import RichLog

    from src.tui.app import SuperMCPApp

    provider = build_provider(PROFILE)
    session = ChatSession(provider, temperature=0, max_tokens=12)
    app = SuperMCPApp(chat=session)
    async with app.run_test() as pilot:
        await pilot.press(*"Say hello")
        await pilot.press("enter")
        await pilot.pause(0.2)
        await app.workers.wait_for_complete()
        await pilot.pause()
        log = "\n".join(line.text for line in app.query_one("#output-log", RichLog).lines)
    assert f"{MODEL}›" in log
    assert session.history[-1].role == "assistant"
    assert session.history[-1].content
    assert session.total_usage.total_tokens > 0
