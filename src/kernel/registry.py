"""Unified registry for skills, tools, and capabilities.

The registry is the single source of truth. Everything discoverable
goes through here. Thread-safe, version-aware, with full audit trail.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
from uuid import UUID

import structlog

from src.kernel.event_bus import EventBus
from src.kernel.types import (
    Capability,
    EntityID,
    Severity,
    SkillCategory,
    SkillDefinition,
    ToolDefinition,
    ToolHealth,
)

logger = structlog.get_logger(__name__)

T = TypeVar("T", SkillDefinition, ToolDefinition)


class Registry(Generic[T]):
    """Generic registry with versioning, indexing, and event emission."""

    def __init__(self, kind: str, event_bus: EventBus) -> None:
        self._kind = kind
        self._bus = event_bus
        self._items: dict[str, T] = {}
        self._versions: dict[str, list[tuple[str, T]]] = defaultdict(list)
        self._tags_index: dict[str, set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def register(self, item: T) -> None:
        slug = item.slug  # type: ignore[attr-defined]
        async with self._lock:
            self._items[slug] = item
            self._versions[slug].append((item.version, item))  # type: ignore[attr-defined]

            for tag in getattr(item, "tags", []):
                self._tags_index[tag].add(slug)

        await self._bus.emit(
            kind=f"{self._kind}.registered",
            source="registry",
            data={"slug": slug, "version": item.version},  # type: ignore[attr-defined]
        )

    async def unregister(self, slug: str) -> T | None:
        async with self._lock:
            item = self._items.pop(slug, None)
            if item:
                for tag in getattr(item, "tags", []):
                    self._tags_index[tag].discard(slug)
                await self._bus.emit(
                    kind=f"{self._kind}.unregistered",
                    source="registry",
                    data={"slug": slug},
                )
            return item

    def get(self, slug: str) -> T | None:
        return self._items.get(slug)

    def get_version(self, slug: str, version: str) -> T | None:
        for v, item in self._versions.get(slug, []):
            if v == version:
                return item
        return None

    def list_all(self) -> list[T]:
        return list(self._items.values())

    def find_by_tag(self, tag: str) -> list[T]:
        slugs = self._tags_index.get(tag, set())
        return [self._items[s] for s in slugs if s in self._items]

    def search(self, query: str) -> list[T]:
        query_lower = query.lower()
        results = []
        for item in self._items.values():
            name = getattr(item, "name", "").lower()
            desc = getattr(item, "description", "").lower()
            tags = [t.lower() for t in getattr(item, "tags", [])]
            if (
                query_lower in name
                or query_lower in desc
                or any(query_lower in t for t in tags)
            ):
                results.append(item)
        return results

    @property
    def count(self) -> int:
        return len(self._items)

    def slugs(self) -> list[str]:
        return list(self._items.keys())


class SkillRegistry(Registry[SkillDefinition]):
    def __init__(self, event_bus: EventBus) -> None:
        super().__init__("skill", event_bus)

    def by_category(self, category: SkillCategory) -> list[SkillDefinition]:
        return [s for s in self._items.values() if s.category == category]

    def composable_with(self, slug: str) -> list[SkillDefinition]:
        skill = self.get(slug)
        if not skill:
            return []
        return [
            self._items[s]
            for s in skill.composable_with
            if s in self._items
        ]

    def dependency_graph(self) -> dict[str, list[str]]:
        """Return {skill_slug: [tool_slugs_it_needs]}."""
        return {
            slug: skill.tool_dependencies
            for slug, skill in self._items.items()
        }


class ToolRegistry(Registry[ToolDefinition]):
    def __init__(self, event_bus: EventBus) -> None:
        super().__init__("tool", event_bus)

    def healthy(self) -> list[ToolDefinition]:
        return [t for t in self._items.values() if t.health == ToolHealth.HEALTHY]

    def by_auth_type(self, auth_type: str) -> list[ToolDefinition]:
        return [t for t in self._items.values() if t.auth_type.value == auth_type]

    def verified(self) -> list[ToolDefinition]:
        return [t for t in self._items.values() if t.verified]

    async def update_health(self, slug: str, health: ToolHealth) -> None:
        tool = self.get(slug)
        if tool:
            old = tool.health
            tool.health = health
            if old != health:
                await self._bus.emit(
                    kind="tool.health_changed",
                    source="registry",
                    data={"slug": slug, "old": old.value, "new": health.value},
                    severity=Severity.WARN if health == ToolHealth.DOWN else Severity.INFO,
                )


class CapabilityNegotiator:
    """Matches agent capabilities against system requirements."""

    def __init__(self, skill_registry: SkillRegistry, tool_registry: ToolRegistry) -> None:
        self._skills = skill_registry
        self._tools = tool_registry

    def negotiate(
        self, capabilities: list[Capability], requested_skills: list[str]
    ) -> dict[str, Any]:
        """Return a negotiation report."""
        cap_names = {c.name for c in capabilities}
        available_tools = {t.slug for t in self._tools.healthy()}

        report: dict[str, Any] = {
            "requested": requested_skills,
            "available": [],
            "unavailable": [],
            "missing_tools": [],
            "missing_capabilities": [],
        }

        for skill_slug in requested_skills:
            skill = self._skills.get(skill_slug)
            if not skill:
                report["unavailable"].append(skill_slug)
                continue

            missing_tools = [
                t for t in skill.tool_dependencies if t not in available_tools
            ]
            if missing_tools:
                report["missing_tools"].extend(missing_tools)
                report["unavailable"].append(skill_slug)
            else:
                report["available"].append(skill_slug)

        return report
