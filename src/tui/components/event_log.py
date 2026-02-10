"""Live event log component — shows kernel events in real-time."""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Label, RichLog, Static


class EventLog(Static):
    """Scrolling event log showing kernel events."""

    MAX_ENTRIES = 500

    def compose(self) -> ComposeResult:
        yield Label("Event Log", classes="panel-title")
        yield RichLog(id="event-log", wrap=True, highlight=True, markup=True)

    def append_event(
        self,
        kind: str,
        source: str,
        severity: str = "info",
        data: dict | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """Append a formatted event entry."""
        log = self.query_one("#event-log", RichLog)
        ts = timestamp or datetime.now()
        ts_str = ts.strftime("%H:%M:%S.%f")[:-3]

        severity_styles = {
            "info": "[dim cyan]",
            "warn": "[bold yellow]",
            "error": "[bold red]",
            "debug": "[dim]",
            "critical": "[bold red reverse]",
        }
        style = severity_styles.get(severity, "[dim]")
        end_style = style.replace("[", "[/").replace("bold ", "").replace("dim ", "").replace("reverse", "")

        text = f"[dim]{ts_str}[/dim] {style}{severity.upper():>5}{end_style} [{source}] {kind}"

        if data:
            detail_parts = []
            for k, v in data.items():
                if isinstance(v, str) and len(v) > 50:
                    v = v[:47] + "..."
                detail_parts.append(f"{k}={v}")
            if detail_parts:
                text += f" [dim]({', '.join(detail_parts)})[/dim]"

        log.write(text)

    def clear(self) -> None:
        log = self.query_one("#event-log", RichLog)
        log.clear()

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
