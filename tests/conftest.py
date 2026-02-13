"""Shared test fixtures for the Super-MCP test suite."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock

import pytest

from src.kernel.types import (
    Artifact,
    Checkpoint,
    EntityID,
    Event,
    EventTopic,
    Session,
    SessionState,
    SkillDefinition,
    ToolDefinition,
    ToolHealth,
)
from src.kernel.event_bus import EventBus
from src.kernel.registry import SkillRegistry, ToolRegistry
from src.kernel.safety import SafetyLayer
from src.kernel.kernel import Kernel
from src.games.engine.state import GameState
from src.games.engine.runner import GameRunner


# ── Event Loop ────────────────────────────────────────


@pytest.fixture(scope="session")
def event_loop():
    """Provide a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Temporary Directories ─────────────────────────────


@pytest.fixture
def tmp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for test artifacts."""
    with tempfile.TemporaryDirectory(prefix="smcp_test_") as d:
        yield Path(d)


@pytest.fixture
def skills_dir(tmp_dir: Path) -> Path:
    """Provide a temporary directory pre-populated with sample skill files."""
    sd = tmp_dir / "skills"
    sd.mkdir()

    for name in ("code-review", "security-audit", "data-analysis"):
        (sd / f"{name}.md").write_text(
            f"---\nname: {name}\nversion: 1.0.0\ntags: [test]\n---\n\n"
            f"# {name.replace('-', ' ').title()}\n\nTest skill.\n"
        )

    return sd


@pytest.fixture
def exports_dir(tmp_dir: Path) -> Path:
    """Provide a temporary directory for exported artifacts."""
    ed = tmp_dir / "exports"
    ed.mkdir()
    return ed


# ── Core Types ────────────────────────────────────────


@pytest.fixture
def sample_skill() -> SkillDefinition:
    """A minimal SkillDefinition for testing."""
    return SkillDefinition(
        name="test-skill",
        description="A skill used in tests",
        version="1.0.0",
        tags=["test", "fixture"],
        parameters=[
            {"name": "input", "type": "string", "required": True},
        ],
        examples=[
            {"input": "hello", "output": "world"},
        ],
    )


@pytest.fixture
def sample_tool() -> ToolDefinition:
    """A minimal ToolDefinition for testing."""
    return ToolDefinition(
        name="test-tool",
        description="A tool used in tests",
        category="testing",
        auth_required=False,
        auth_scopes=[],
        health_check_url="https://httpbin.org/get",
        health=ToolHealth.HEALTHY,
        version="1.0.0",
        tags=["test", "fixture"],
    )


@pytest.fixture
def sample_event() -> Event:
    """A minimal Event for testing."""
    return Event(
        source="test",
        topic=EventTopic.SYSTEM,
        action="test.action",
        payload={"key": "value"},
    )


@pytest.fixture
def sample_checkpoint() -> Checkpoint:
    """A minimal Checkpoint for testing."""
    return Checkpoint(
        name="test-checkpoint",
        state={"counter": 42, "items": ["a", "b"]},
    )


@pytest.fixture
def sample_artifact(tmp_dir: Path) -> Artifact:
    """A minimal Artifact for testing."""
    return Artifact(
        name="test-artifact",
        content="# Test Artifact\n\nHello, world.\n",
        format="md",
        tags=["test"],
    )


@pytest.fixture
def sample_session() -> Session:
    """A minimal Session for testing."""
    return Session(
        state=SessionState.RUNNING,
    )


# ── Kernel Components ─────────────────────────────────


@pytest.fixture
def event_bus() -> EventBus:
    """A fresh EventBus instance."""
    return EventBus(buffer_size=1000)


@pytest.fixture
def skill_registry() -> SkillRegistry:
    """A fresh SkillRegistry instance."""
    return SkillRegistry()


@pytest.fixture
def tool_registry() -> ToolRegistry:
    """A fresh ToolRegistry instance."""
    return ToolRegistry()


@pytest.fixture
def safety_layer() -> SafetyLayer:
    """A SafetyLayer with default rules."""
    return SafetyLayer()


@pytest.fixture
async def kernel() -> AsyncGenerator[Kernel, None]:
    """A booted Kernel instance. Shuts down after the test."""
    k = Kernel()
    await k.boot()
    yield k
    await k.shutdown()


# ── Game Fixtures ─────────────────────────────────────


@pytest.fixture
def game_state() -> GameState:
    """A fresh GameState instance."""
    return GameState(max_undo=50)


@pytest.fixture
def game_runner() -> GameRunner:
    """A GameRunner with no games registered."""
    return GameRunner()


# ── Mock Fixtures ─────────────────────────────────────


@pytest.fixture
def mock_event_callback() -> AsyncMock:
    """An AsyncMock suitable for event bus subscription."""
    return AsyncMock()


@pytest.fixture
def mock_llm_response() -> dict:
    """A mock LLM response payload for testing tool/skill integrations."""
    return {
        "id": "mock-response-001",
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "This is a mock response for testing.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        },
    }


# ── Helpers ───────────────────────────────────────────


@pytest.fixture
def make_skills(skill_registry: SkillRegistry):
    """Factory fixture: register N skills and return them."""

    def _make(count: int = 5) -> list[SkillDefinition]:
        skills = []
        for i in range(count):
            s = SkillDefinition(
                name=f"skill-{i}",
                description=f"Generated skill {i}",
                version="1.0.0",
                tags=["generated", f"batch-{i % 3}"],
                parameters=[],
                examples=[],
            )
            skill_registry.register(s)
            skills.append(s)
        return skills

    return _make


@pytest.fixture
def make_tools(tool_registry: ToolRegistry):
    """Factory fixture: register N tools and return them."""

    def _make(count: int = 5) -> list[ToolDefinition]:
        tools = []
        for i in range(count):
            t = ToolDefinition(
                name=f"tool-{i}",
                description=f"Generated tool {i}",
                category="generated",
                auth_required=False,
                auth_scopes=[],
                health_check_url=f"https://example.com/tool-{i}/health",
                health=ToolHealth.HEALTHY,
                version="1.0.0",
                tags=["generated"],
            )
            tool_registry.register(t)
            tools.append(t)
        return tools

    return _make


@pytest.fixture
def make_events():
    """Factory fixture: generate N events."""

    def _make(count: int = 10, topic: EventTopic = EventTopic.SYSTEM) -> list[Event]:
        return [
            Event(
                source="test-factory",
                topic=topic,
                action=f"action.{i}",
                payload={"index": i},
            )
            for i in range(count)
        ]

    return _make
