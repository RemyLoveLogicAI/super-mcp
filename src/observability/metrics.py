"""Observability — structured metrics, logging, and tracing.

Provides Prometheus-compatible metrics, structured JSON logging
configuration, and OpenTelemetry-compatible trace spans.
"""

from __future__ import annotations

import time
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator
from uuid import uuid4

import structlog

logger = structlog.get_logger(__name__)


# ── Metric types ─────────────────────────────────────────────────────

@dataclass
class MetricPoint:
    """Single metric observation."""
    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class Counter:
    """Monotonically increasing counter."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._values: defaultdict[tuple, float] = defaultdict(float)

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        self._values[key] += amount

    def get(self, **labels: str) -> float:
        key = tuple(sorted(labels.items()))
        return self._values[key]

    @property
    def total(self) -> float:
        return sum(self._values.values())

    def collect(self) -> list[MetricPoint]:
        return [
            MetricPoint(
                name=self.name,
                value=val,
                labels=dict(key),
            )
            for key, val in self._values.items()
        ]


class Gauge:
    """Value that can go up and down."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._values: defaultdict[tuple, float] = defaultdict(float)

    def set(self, value: float, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        self._values[key] = value

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        self._values[key] += amount

    def dec(self, amount: float = 1.0, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        self._values[key] -= amount

    def get(self, **labels: str) -> float:
        key = tuple(sorted(labels.items()))
        return self._values[key]

    def collect(self) -> list[MetricPoint]:
        return [
            MetricPoint(name=self.name, value=val, labels=dict(key))
            for key, val in self._values.items()
        ]


class Histogram:
    """Distribution of observations across buckets."""

    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(
        self,
        name: str,
        description: str = "",
        buckets: tuple[float, ...] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self._buckets = buckets or self.DEFAULT_BUCKETS
        self._observations: defaultdict[tuple, list[float]] = defaultdict(list)

    def observe(self, value: float, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        self._observations[key].append(value)

    def percentile(self, p: float, **labels: str) -> float:
        """Get the p-th percentile (0-100)."""
        key = tuple(sorted(labels.items()))
        obs = sorted(self._observations.get(key, []))
        if not obs:
            return 0.0
        idx = int(len(obs) * p / 100)
        return obs[min(idx, len(obs) - 1)]

    def count(self, **labels: str) -> int:
        key = tuple(sorted(labels.items()))
        return len(self._observations.get(key, []))

    def sum(self, **labels: str) -> float:
        key = tuple(sorted(labels.items()))
        return sum(self._observations.get(key, []))

    def collect(self) -> list[MetricPoint]:
        points = []
        for key, obs in self._observations.items():
            labels = dict(key)
            points.append(MetricPoint(name=f"{self.name}_count", value=len(obs), labels=labels))
            points.append(MetricPoint(name=f"{self.name}_sum", value=sum(obs), labels=labels))
            for bucket in self._buckets:
                count = sum(1 for v in obs if v <= bucket)
                points.append(MetricPoint(
                    name=f"{self.name}_bucket",
                    value=count,
                    labels={**labels, "le": str(bucket)},
                ))
        return points


# ── Trace spans ──────────────────────────────────────────────────────

@dataclass
class Span:
    """OpenTelemetry-compatible trace span."""
    trace_id: str
    span_id: str
    name: str
    parent_id: str | None = None
    start_time: float = field(default_factory=time.monotonic)
    end_time: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    status: str = "OK"

    @property
    def duration_ms(self) -> float:
        if self.end_time is None:
            return (time.monotonic() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": time.monotonic(),
            "attributes": attributes or {},
        })

    def finish(self, status: str = "OK") -> None:
        self.end_time = time.monotonic()
        self.status = status

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "name": self.name,
            "parent_id": self.parent_id,
            "duration_ms": round(self.duration_ms, 3),
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
        }


# ── Metrics Registry ─────────────────────────────────────────────────

class MetricsRegistry:
    """Central metrics registry for the Super-MCP system."""

    def __init__(self) -> None:
        # Counters
        self.skill_invocations = Counter("smcp_skill_invocations_total", "Total skill invocations")
        self.tool_invocations = Counter("smcp_tool_invocations_total", "Total tool invocations")
        self.events_emitted = Counter("smcp_events_emitted_total", "Total events emitted")
        self.errors = Counter("smcp_errors_total", "Total errors")
        self.safety_blocks = Counter("smcp_safety_blocks_total", "Safety layer blocks")
        self.game_actions = Counter("smcp_game_actions_total", "Game actions processed")

        # Gauges
        self.active_sessions = Gauge("smcp_active_sessions", "Active sessions")
        self.registered_skills = Gauge("smcp_registered_skills", "Registered skills")
        self.registered_tools = Gauge("smcp_registered_tools", "Registered tools")
        self.healthy_tools = Gauge("smcp_healthy_tools", "Healthy tools")

        # Histograms
        self.skill_duration = Histogram("smcp_skill_duration_seconds", "Skill execution duration")
        self.tool_duration = Histogram("smcp_tool_duration_seconds", "Tool execution duration")
        self.event_processing = Histogram("smcp_event_processing_seconds", "Event processing duration")

        # Traces
        self._spans: list[Span] = []
        self._active_traces: dict[str, str] = {}  # trace_id → root_span_id

    def create_span(
        self,
        name: str,
        parent_id: str | None = None,
        trace_id: str | None = None,
        **attributes: Any,
    ) -> Span:
        """Create a new trace span."""
        span = Span(
            trace_id=trace_id or uuid4().hex[:16],
            span_id=uuid4().hex[:16],
            name=name,
            parent_id=parent_id,
            attributes=attributes,
        )
        self._spans.append(span)
        return span

    @asynccontextmanager
    async def trace(
        self,
        name: str,
        parent_id: str | None = None,
        **attributes: Any,
    ) -> AsyncIterator[Span]:
        """Context manager for tracing an operation."""
        span = self.create_span(name, parent_id=parent_id, **attributes)
        try:
            yield span
            span.finish("OK")
        except Exception as e:
            span.finish("ERROR")
            span.add_event("exception", {"type": type(e).__name__, "message": str(e)})
            raise

    def get_recent_spans(self, limit: int = 50) -> list[Span]:
        """Get most recent spans."""
        return self._spans[-limit:]

    def collect_all(self) -> list[MetricPoint]:
        """Collect all metric points."""
        points: list[MetricPoint] = []
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if isinstance(attr, (Counter, Gauge, Histogram)):
                points.extend(attr.collect())
        return points

    def format_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines: list[str] = []
        for point in self.collect_all():
            label_str = ""
            if point.labels:
                pairs = [f'{k}="{v}"' for k, v in point.labels.items()]
                label_str = "{" + ",".join(pairs) + "}"
            lines.append(f"{point.name}{label_str} {point.value}")
        return "\n".join(lines)

    @property
    def summary(self) -> dict[str, Any]:
        """Quick summary of key metrics."""
        return {
            "skill_invocations": self.skill_invocations.total,
            "tool_invocations": self.tool_invocations.total,
            "events_emitted": self.events_emitted.total,
            "errors": self.errors.total,
            "safety_blocks": self.safety_blocks.total,
            "game_actions": self.game_actions.total,
            "active_spans": len([s for s in self._spans if s.end_time is None]),
            "total_spans": len(self._spans),
        }
