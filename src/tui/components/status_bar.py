"""Status bar component — bottom status indicators."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widgets import Label, Static


class StatusBar(Static):
    """Bottom status bar with mode, health, and key hints."""

    mode = reactive("COMMAND")
    health_text = reactive("")
    hint_text = reactive("F1:Help  F2:Skills  F3:Tools  F4:Games  F5:Events  Ctrl+Q:Quit")

    def compose(self) -> ComposeResult:
        yield Label("", id="status-mode")
        yield Label("", id="status-health")
        yield Label("", id="status-hints")

    def on_mount(self) -> None:
        self._update_all()

    def watch_mode(self, value: str) -> None:
        self._update_all()

    def watch_health_text(self, value: str) -> None:
        self._update_all()

    def watch_hint_text(self, value: str) -> None:
        self._update_all()

    def _update_all(self) -> None:
        try:
            mode_label = self.query_one("#status-mode", Label)
            health_label = self.query_one("#status-health", Label)
            hint_label = self.query_one("#status-hints", Label)

            mode_colors = {
                "COMMAND": "bold white on dark_blue",
                "GAME": "bold white on dark_green",
                "ONBOARDING": "bold white on dark_magenta",
            }
            color = mode_colors.get(self.mode, "bold white on dark_blue")
            mode_label.update(f" [{color}] {self.mode} [/{color}] ")

            if self.health_text:
                health_label.update(f"  {self.health_text}")
            else:
                health_label.update("")

            hint_label.update(self.hint_text)
        except Exception:
            pass

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
