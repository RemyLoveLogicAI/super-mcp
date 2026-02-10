"""Extensibility Hooks — plugin and extension points.

Provides a hook system for extending Super-MCP without modifying
core code. Plugins can register before/after hooks on skills,
tools, events, and lifecycle transitions.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

import structlog

logger = structlog.get_logger(__name__)

HookCallback = Callable[..., Coroutine[Any, Any, Any]]


@dataclass
class Hook:
    """Registered hook definition."""
    name: str
    callback: HookCallback
    priority: int = 100  # Lower = runs first
    plugin_id: str = "core"
    enabled: bool = True


@dataclass
class HookResult:
    """Result from hook execution."""
    hook_name: str
    success: bool
    data: Any = None
    error: str | None = None


class HookRegistry:
    """Central registry for extension hooks."""

    HOOK_POINTS = [
        # Lifecycle
        "kernel.before_boot",
        "kernel.after_boot",
        "kernel.before_shutdown",
        "kernel.after_shutdown",
        # Skills
        "skill.before_register",
        "skill.after_register",
        "skill.before_execute",
        "skill.after_execute",
        # Tools
        "tool.before_register",
        "tool.after_register",
        "tool.before_invoke",
        "tool.after_invoke",
        "tool.on_health_change",
        # Events
        "event.before_emit",
        "event.after_emit",
        # Safety
        "safety.before_evaluate",
        "safety.after_evaluate",
        "safety.on_block",
        # Session
        "session.on_state_change",
        "session.on_checkpoint",
        # Games
        "game.before_start",
        "game.after_end",
        "game.on_action",
        # Onboarding
        "onboarding.before_step",
        "onboarding.after_step",
        "onboarding.on_complete",
    ]

    def __init__(self) -> None:
        self._hooks: defaultdict[str, list[Hook]] = defaultdict(list)
        self._plugins: dict[str, dict[str, Any]] = {}

    def register_plugin(self, plugin_id: str, metadata: dict[str, Any] | None = None) -> None:
        """Register a plugin with the hook system."""
        self._plugins[plugin_id] = metadata or {}

    def register(
        self,
        hook_point: str,
        callback: HookCallback,
        priority: int = 100,
        plugin_id: str = "core",
    ) -> Hook:
        """Register a hook at an extension point."""
        hook = Hook(
            name=hook_point,
            callback=callback,
            priority=priority,
            plugin_id=plugin_id,
        )
        self._hooks[hook_point].append(hook)
        # Keep sorted by priority
        self._hooks[hook_point].sort(key=lambda h: h.priority)
        return hook

    def unregister(self, hook_point: str, plugin_id: str) -> int:
        """Remove all hooks from a plugin at a hook point."""
        before = len(self._hooks[hook_point])
        self._hooks[hook_point] = [
            h for h in self._hooks[hook_point] if h.plugin_id != plugin_id
        ]
        return before - len(self._hooks[hook_point])

    async def trigger(
        self,
        hook_point: str,
        context: dict[str, Any] | None = None,
    ) -> list[HookResult]:
        """Trigger all hooks at a hook point."""
        results: list[HookResult] = []
        hooks = self._hooks.get(hook_point, [])

        for hook in hooks:
            if not hook.enabled:
                continue
            try:
                data = await hook.callback(context or {})
                results.append(HookResult(
                    hook_name=f"{hook.plugin_id}:{hook.name}",
                    success=True,
                    data=data,
                ))
            except Exception as e:
                results.append(HookResult(
                    hook_name=f"{hook.plugin_id}:{hook.name}",
                    success=False,
                    error=str(e),
                ))
                await logger.awarn(
                    "hook_execution_failed",
                    hook=hook.name,
                    plugin=hook.plugin_id,
                    error=str(e),
                )

        return results

    def list_hooks(self, hook_point: str | None = None) -> dict[str, list[dict[str, Any]]]:
        """List registered hooks."""
        points = [hook_point] if hook_point else list(self._hooks.keys())
        result: dict[str, list[dict[str, Any]]] = {}
        for point in points:
            result[point] = [
                {
                    "plugin_id": h.plugin_id,
                    "priority": h.priority,
                    "enabled": h.enabled,
                }
                for h in self._hooks.get(point, [])
            ]
        return result

    @property
    def stats(self) -> dict[str, Any]:
        total = sum(len(hooks) for hooks in self._hooks.values())
        return {
            "total_hooks": total,
            "hook_points_used": len(self._hooks),
            "plugins": list(self._plugins.keys()),
        }
