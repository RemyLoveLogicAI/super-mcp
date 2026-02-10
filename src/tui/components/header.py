"""Header bar component."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Label, Static


class HeaderBar(Static):
    """Top header bar showing title and session info."""

    session_state = reactive("INITIALIZING")
    skill_count = reactive(0)
    tool_count = reactive(0)

    def compose(self) -> ComposeResult:
        with Horizontal(id="header-content"):
            yield Label("⚡ SUPER-MCP", id="header-title")
            yield Label("", id="header-session")
            yield Label("", id="header-stats")

    def watch_session_state(self, value: str) -> None:
        label = self.query_one("#header-session", Label)
        label.update(f"  │  Session: {value}")

    def watch_skill_count(self, value: int) -> None:
        self._update_stats()

    def watch_tool_count(self, value: int) -> None:
        self._update_stats()

    def _update_stats(self) -> None:
        try:
            label = self.query_one("#header-stats", Label)
            label.update(f"  │  Skills: {self.skill_count}  Tools: {self.tool_count}")
        except Exception:
            pass

    DEFAULT_CSS = """
    HeaderBar {
        dock: top;
        height: 3;
        background: #1a1a2e;
        padding: 1 2;
    }

    #header-content {
        height: 1;
    }

    #header-title {
        color: #7c3aed;
        text-style: bold;
        width: auto;
    }

    #header-session {
        color: #94a3b8;
        width: auto;
    }

    #header-stats {
        color: #64748b;
        width: auto;
        dock: right;
    }
    """
