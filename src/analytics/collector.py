"""Analytics Collector — skill/tool usage tracking and reporting.

Captures structured usage data for skills, tools, and sessions.
Provides aggregation, trend analysis, and exportable reports.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import structlog

from src.kernel.event_bus import EventBus
from src.kernel.types import Event

logger = structlog.get_logger(__name__)


@dataclass
class UsageRecord:
    """Single usage event."""
    entity_type: str  # "skill", "tool", "game", "command"
    entity_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageReport:
    """Aggregated usage statistics."""
    period_start: datetime
    period_end: datetime
    total_events: int = 0
    skill_usage: dict[str, int] = field(default_factory=dict)
    tool_usage: dict[str, int] = field(default_factory=dict)
    game_usage: dict[str, int] = field(default_factory=dict)
    error_count: int = 0
    avg_duration_ms: float = 0.0
    top_skills: list[tuple[str, int]] = field(default_factory=list)
    top_tools: list[tuple[str, int]] = field(default_factory=list)
    sessions: int = 0
    unique_entities: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat(),
            },
            "total_events": self.total_events,
            "error_count": self.error_count,
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "skill_usage": self.skill_usage,
            "tool_usage": self.tool_usage,
            "game_usage": self.game_usage,
            "top_skills": self.top_skills,
            "top_tools": self.top_tools,
            "sessions": self.sessions,
            "unique_entities": self.unique_entities,
        }


class AnalyticsCollector:
    """Collects and aggregates usage analytics."""

    def __init__(self, event_bus: EventBus, storage_dir: Path | None = None) -> None:
        self._event_bus = event_bus
        self._storage_dir = storage_dir or Path.home() / ".super-mcp" / "analytics"
        self._records: list[UsageRecord] = []
        self._active = False

    @property
    def record_count(self) -> int:
        return len(self._records)

    async def start(self) -> None:
        """Start collecting analytics."""
        self._active = True
        self._event_bus.subscribe_all(self._on_event)
        await logger.ainfo("analytics_started")

    async def stop(self) -> None:
        """Stop collecting."""
        self._active = False
        await logger.ainfo("analytics_stopped", records=len(self._records))

    async def _on_event(self, event: Event) -> None:
        """Process kernel events into usage records."""
        if not self._active:
            return

        kind = event.kind
        data = event.data or {}

        if kind.startswith("skill."):
            self._records.append(UsageRecord(
                entity_type="skill",
                entity_id=data.get("skill_slug", kind),
                timestamp=event.timestamp,
                duration_ms=data.get("duration_ms", 0),
                success=data.get("success", True),
                metadata=data,
            ))
        elif kind.startswith("tool."):
            self._records.append(UsageRecord(
                entity_type="tool",
                entity_id=data.get("tool_slug", kind),
                timestamp=event.timestamp,
                duration_ms=data.get("duration_ms", 0),
                success=data.get("success", True),
                metadata=data,
            ))
        elif kind.startswith("game."):
            self._records.append(UsageRecord(
                entity_type="game",
                entity_id=data.get("game_type", kind),
                timestamp=event.timestamp,
                metadata=data,
            ))
        elif kind.startswith("action."):
            self._records.append(UsageRecord(
                entity_type="command",
                entity_id=data.get("action", kind),
                timestamp=event.timestamp,
                success="blocked" not in kind,
                metadata=data,
            ))

    def record(self, entity_type: str, entity_id: str, **kwargs: Any) -> None:
        """Manually record a usage event."""
        self._records.append(UsageRecord(
            entity_type=entity_type,
            entity_id=entity_id,
            **kwargs,
        ))

    def generate_report(
        self,
        period_hours: int = 24,
        entity_type: str | None = None,
    ) -> UsageReport:
        """Generate aggregated report for the given period."""
        now = datetime.now()
        cutoff = now - timedelta(hours=period_hours)

        filtered = [
            r for r in self._records
            if r.timestamp >= cutoff
            and (entity_type is None or r.entity_type == entity_type)
        ]

        skill_counter: Counter[str] = Counter()
        tool_counter: Counter[str] = Counter()
        game_counter: Counter[str] = Counter()
        durations: list[float] = []
        errors = 0
        entities: set[str] = set()

        for record in filtered:
            entities.add(f"{record.entity_type}:{record.entity_id}")

            if record.entity_type == "skill":
                skill_counter[record.entity_id] += 1
            elif record.entity_type == "tool":
                tool_counter[record.entity_id] += 1
            elif record.entity_type == "game":
                game_counter[record.entity_id] += 1

            if record.duration_ms > 0:
                durations.append(record.duration_ms)
            if not record.success:
                errors += 1

        return UsageReport(
            period_start=cutoff,
            period_end=now,
            total_events=len(filtered),
            skill_usage=dict(skill_counter),
            tool_usage=dict(tool_counter),
            game_usage=dict(game_counter),
            error_count=errors,
            avg_duration_ms=sum(durations) / len(durations) if durations else 0,
            top_skills=skill_counter.most_common(10),
            top_tools=tool_counter.most_common(10),
            unique_entities=len(entities),
        )

    async def export_report(self, report: UsageReport, filename: str | None = None) -> Path:
        """Export report to JSON."""
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        if not filename:
            filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path = self._storage_dir / filename
        path.write_text(json.dumps(report.to_dict(), indent=2, default=str), encoding="utf-8")
        await logger.ainfo("analytics_exported", path=str(path))
        return path

    def get_trend(self, entity_type: str, entity_id: str, days: int = 7) -> list[tuple[str, int]]:
        """Get daily usage trend for an entity."""
        now = datetime.now()
        cutoff = now - timedelta(days=days)

        daily: defaultdict[str, int] = defaultdict(int)
        for record in self._records:
            if (record.entity_type == entity_type
                    and record.entity_id == entity_id
                    and record.timestamp >= cutoff):
                day_key = record.timestamp.strftime("%Y-%m-%d")
                daily[day_key] += 1

        # Fill in missing days
        result = []
        for i in range(days):
            day = (cutoff + timedelta(days=i + 1)).strftime("%Y-%m-%d")
            result.append((day, daily.get(day, 0)))

        return result
