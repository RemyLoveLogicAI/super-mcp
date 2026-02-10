"""API — extensibility hooks and plugin system."""

from src.api.hooks import Hook, HookRegistry, HookResult

__all__ = ["Hook", "HookRegistry", "HookResult"]
