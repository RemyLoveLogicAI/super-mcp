"""Shared test fixtures for the Super-MCP test suite.

The previous fixture set referenced kernel types and constructor signatures
that no longer exist (``EventTopic``, ``EventBus(buffer_size=...)``), which
made every test module fail at import. These fixtures match the current code.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from src.games.engine.runner import GameRunner
from src.kernel.event_bus import EventBus
from src.kernel.kernel import Kernel

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator


@pytest.fixture
def tmp_dir() -> Generator[Path, None, None]:
    """A temporary directory for test artifacts."""
    with tempfile.TemporaryDirectory(prefix="smcp_test_") as d:
        yield Path(d)


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus(max_history=1000)


@pytest.fixture
async def kernel() -> AsyncGenerator[Kernel, None]:
    """A booted Kernel instance, shut down after the test."""
    k = Kernel()
    await k.boot()
    yield k
    await k.shutdown()


@pytest.fixture
def game_runner(event_bus: EventBus) -> GameRunner:
    return GameRunner(event_bus)
