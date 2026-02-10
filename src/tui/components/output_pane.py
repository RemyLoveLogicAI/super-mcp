"""Output pane — main content display area."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import RichLog, Static, Label


class OutputPane(Static):
    """Main output display for commands, game text, and responses."""

    def compose(self) -> ComposeResult:
        yield RichLog(id="output-log", wrap=True, highlight=True, markup=True)

    def write(self, text: str, style: str = "") -> None:
        """Write text to the output pane."""
        log = self.query_one("#output-log", RichLog)
        if style:
            log.write(f"[{style}]{text}[/{style}]")
        else:
            log.write(text)

    def write_system(self, text: str) -> None:
        """Write system message."""
        self.write(text, "dim cyan")

    def write_error(self, text: str) -> None:
        """Write error message."""
        self.write(text, "bold red")

    def write_success(self, text: str) -> None:
        """Write success message."""
        self.write(text, "bold green")

    def write_game(self, text: str) -> None:
        """Write game output."""
        self.write(text)

    def clear(self) -> None:
        log = self.query_one("#output-log", RichLog)
        log.clear()

    DEFAULT_CSS = """
    OutputPane {
        height: 1fr;
        background: #0f172a;
        padding: 0;
    }

    #output-log {
        height: 1fr;
        padding: 1 2;
        scrollbar-size: 1 1;
    }
    """
