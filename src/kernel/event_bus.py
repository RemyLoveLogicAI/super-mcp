"""Lock-free, async event bus with replay support.

Events flow through here. Every subsystem publishes and subscribes.
The bus maintains a bounded ring buffer for replay and audit.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from typing import Any, Callable, Coroutine
from uuid import UUID

import structlog

from src.kernel.types import Event, Severity

logger = structlog.get_logger(__name__)

Listener = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Async event bus with topic-based pub/sub and bounded history."""

    __slots__ = ("_listeners", "_history", "_max_history", "_lock", "_running")

    def __init__(self, max_history: int = 10_000) -> None:
        self._listeners: dict[str, list[Listener]] = defaultdict(list)
        self._history: deque[Event] = deque(maxlen=max_history)
        self._max_history = max_history
        self._lock = asyncio.Lock()
        self._running = True

    def subscribe(self, kind: str, listener: Listener) -> None:
        self._listeners[kind].append(listener)

    def subscribe_all(self, listener: Listener) -> None:
        self._listeners["*"].append(listener)

    def unsubscribe(self, kind: str, listener: Listener) -> None:
        if kind in self._listeners:
            self._listeners[kind] = [l for l in self._listeners[kind] if l is not listener]

    async def publish(self, event: Event) -> None:
        if not self._running:
            return

        self._history.append(event)

        targets = list(self._listeners.get(event.kind, []))
        targets.extend(self._listeners.get("*", []))

        if not targets:
            return

        results = await asyncio.gather(
            *[self._safe_dispatch(listener, event) for listener in targets],
            return_exceptions=True,
        )

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                await logger.aerror(
                    "event_listener_failed",
                    kind=event.kind,
                    listener=str(targets[i]),
                    error=str(result),
                )

    async def emit(
        self,
        kind: str,
        source: str,
        data: dict[str, Any] | None = None,
        severity: Severity = Severity.INFO,
        correlation_id: UUID | None = None,
    ) -> Event:
        """Convenience: build + publish in one call."""
        event = Event(
            kind=kind,
            source=source,
            data=data or {},
            severity=severity,
            correlation_id=correlation_id,
        )
        await self.publish(event)
        return event

    def history(
        self,
        kind: str | None = None,
        limit: int = 100,
        correlation_id: UUID | None = None,
    ) -> list[Event]:
        """Query the event ring buffer."""
        events = list(self._history)
        if kind:
            events = [e for e in events if e.kind == kind]
        if correlation_id:
            events = [e for e in events if e.correlation_id == correlation_id]
        return events[-limit:]

    def replay_from(self, sequence_start: int) -> list[Event]:
        """Return events from index onward (for checkpoint replay)."""
        all_events = list(self._history)
        return all_events[sequence_start:]

    def clear(self) -> None:
        self._history.clear()

    def stop(self) -> None:
        self._running = False

    @property
    def event_count(self) -> int:
        return len(self._history)

    @staticmethod
    async def _safe_dispatch(listener: Listener, event: Event) -> None:
        try:
            await listener(event)
        except Exception:
            raise
