"""Output pane — main content display area, including live model streaming."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual.widgets import RichLog, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult


class OutputPane(Static):
    """Main output display for commands, game text, and model responses.

    ``write*`` methods accept Rich markup for trusted, app-authored text.
    Untrusted text (user input, model output) goes through :meth:`write_plain`
    or the streaming methods, which never interpret markup.
    """

    def __init__(self) -> None:
        super().__init__()
        self._stream_label = ""
        self._stream_parts: list[str] = []

    def compose(self) -> ComposeResult:
        yield RichLog(id="output-log", wrap=True, highlight=False, markup=True)
        yield Static("", id="output-stream", markup=False)

    def _log(self) -> RichLog:
        return self.query_one("#output-log", RichLog)

    def write(self, text: str, style: str = "") -> None:
        """Write app-authored text (Rich markup allowed)."""
        self._log().write(f"[{style}]{text}[/{style}]" if style else text)

    def write_plain(self, text: str, style: str = "") -> None:
        """Write untrusted text verbatim; brackets are not markup."""
        self._log().write(Text(text, style=style))

    def write_system(self, text: str) -> None:
        self.write(text, "dim cyan")

    def write_error(self, text: str) -> None:
        self.write_plain(text, "bold red")

    def write_success(self, text: str) -> None:
        self.write(text, "bold green")

    def write_game(self, text: str) -> None:
        self.write_plain(text)

    # ── Streaming ───────────────────────────────────────────────

    @property
    def streaming(self) -> bool:
        return bool(self._stream_label)

    def begin_stream(self, label: str) -> None:
        """Start a live response block headed by ``label``."""
        self._stream_label = label
        self._stream_parts = []
        stream = self.query_one("#output-stream", Static)
        stream.update(Text(f"{label} ", style="bold magenta"))
        stream.display = True

    def append_stream(self, text: str) -> None:
        if not self._stream_label:
            return
        self._stream_parts.append(text)
        body = Text(f"{self._stream_label} ", style="bold magenta")
        body.append("".join(self._stream_parts))
        self.query_one("#output-stream", Static).update(body)

    def end_stream(self, suffix: str = "") -> str:
        """Commit the live block to the log and return the streamed text."""
        if not self._stream_label:
            return ""
        full = "".join(self._stream_parts)
        line = Text(f"{self._stream_label} ", style="bold magenta")
        line.append(full)
        if suffix:
            line.append(f" {suffix}", style="dim yellow")
        self._log().write(line)
        stream = self.query_one("#output-stream", Static)
        stream.update("")
        stream.display = False
        self._stream_label = ""
        self._stream_parts = []
        return full

    def clear(self) -> None:
        self._log().clear()

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

    #output-stream {
        display: none;
        height: auto;
        max-height: 60%;
        padding: 0 2 1 2;
        color: #f8fafc;
    }
    """
