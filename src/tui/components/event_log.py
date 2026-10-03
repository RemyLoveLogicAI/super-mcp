"""Live event log component — shows kernel events in real-time."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from rich.markup import escape
from textual.widgets import Label, RichLog, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult

_SEVERITY_STYLES = {
    "info": "dim cyan",
    "warn": "bold yellow",
    "error": "bold red",
    "fatal": "bold red reverse",
    "debug": "dim",
    "trace": "dim",
}


class EventLog(Static):
    """Scrolling event log showing kernel events."""

    MAX_ENTRIES = 500

    def compose(self) -> ComposeResult:
        yield Label("Event Log", classes="panel-title")
        yield RichLog(id="event-log", wrap=True, highlight=False, markup=True)

    def append_event(
        self,
        kind: str,
        source: str,
        severity: str = "info",
        data: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """Append a formatted event entry (all event fields are escaped)."""
        log = self.query_one("#event-log", RichLog)
        ts = (timestamp or datetime.now(UTC)).astimezone()
        ts_str = ts.strftime("%H:%M:%S.%f")[:-3]
        style = _SEVERITY_STYLES.get(severity, "dim")
        text = (
            f"[dim]{ts_str}[/dim] [{style}]{escape(severity.upper()):>5}[/{style}] "
            f"\\[{escape(source)}] {escape(kind)}"
        )
        if data:
            parts = []
            for k, v in data.items():
                value = str(v)
                if len(value) > 50:
                    value = value[:47] + "..."
                parts.append(f"{k}={value}")
            text += f" [dim]({escape(', '.join(parts))})[/dim]"
        log.write(text)

    def clear(self) -> None:
        self.query_one("#event-log", RichLog).clear()

    DEFAULT_CSS = """
    EventLog {
        height: 12;
        background: #0a0a1a;
        border-top: solid #334155;
        padding: 0 1;
    }

    #event-log {
        height: 1fr;
        scrollbar-size: 1 1;
    }
    """
