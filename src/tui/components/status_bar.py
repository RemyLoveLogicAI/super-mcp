"""Status bar component — bottom status indicators."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.reactive import reactive
from textual.widgets import Label, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult

MODE_COLORS = {
    "COMMAND": "bold white on dark_blue",
    "GAME": "bold white on dark_green",
    "ONBOARDING": "bold white on dark_magenta",
    "STREAMING": "bold black on yellow",
}


class StatusBar(Static):
    """Bottom status bar with mode, health/provider info, and key hints."""

    mode = reactive("COMMAND")
    health_text = reactive("")
    hint_text = reactive(
        "F1:Help  F2:Skills  F3:Tools  F4:Games  F5:Events  Esc:Cancel  Ctrl+Q:Quit"
    )

    def compose(self) -> ComposeResult:
        yield Label("", id="status-mode")
        yield Label("", id="status-health", markup=False)
        yield Label("", id="status-hints")

    def on_mount(self) -> None:
        self._update_all()

    def watch_mode(self) -> None:
        self._update_all()

    def watch_health_text(self) -> None:
        self._update_all()

    def watch_hint_text(self) -> None:
        self._update_all()

    def _update_all(self) -> None:
        if not self.is_mounted:
            return
        color = MODE_COLORS.get(self.mode, MODE_COLORS["COMMAND"])
        self.query_one("#status-mode", Label).update(f" [{color}] {self.mode} [/{color}] ")
        self.query_one("#status-health", Label).update(
            f"  {self.health_text}" if self.health_text else ""
        )
        self.query_one("#status-hints", Label).update(self.hint_text)

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: #1a1a2e;
        layout: horizontal;
        padding: 0 1;
    }

    #status-mode {
        width: auto;
        color: #f8fafc;
    }

    #status-health {
        width: auto;
        color: #10b981;
    }

    #status-hints {
        width: 1fr;
        color: #64748b;
        text-align: right;
    }
    """
