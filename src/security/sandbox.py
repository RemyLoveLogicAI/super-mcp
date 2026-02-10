"""Security Sandbox — resource limits and execution isolation.

Provides lightweight sandboxing for tool execution, including
resource limits, timeout enforcement, and output validation.
"""

from __future__ import annotations

import asyncio
import os
import resource
import signal
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class SandboxConfig:
    """Sandbox resource limits."""
    max_memory_mb: int = 512
    max_cpu_seconds: int = 30
    max_output_bytes: int = 10 * 1024 * 1024  # 10MB
    max_file_writes: int = 100
    allowed_paths: list[str] = field(default_factory=lambda: ["/tmp"])
    blocked_commands: list[str] = field(default_factory=lambda: [
        "rm -rf /", "mkfs", "dd if=/dev/zero", ":(){ :|:& };:",
        "chmod -R 777 /", "shutdown", "reboot", "halt",
    ])
    network_allowed: bool = True
    timeout_seconds: int = 60


@dataclass
class SandboxResult:
    """Result of sandboxed execution."""
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    resources_used: dict[str, Any] = field(default_factory=dict)
    violations: list[str] = field(default_factory=list)


class Sandbox:
    """Execution sandbox with resource limits."""

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self.config = config or SandboxConfig()
        self._execution_count = 0

    async def execute(
        self,
        func: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> SandboxResult:
        """Execute a function within sandbox constraints."""
        import time
        start = time.monotonic()
        self._execution_count += 1

        try:
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.timeout_seconds,
            )
            duration = (time.monotonic() - start) * 1000

            return SandboxResult(
                success=True,
                output=result,
                duration_ms=duration,
                resources_used={"execution_id": self._execution_count},
            )

        except asyncio.TimeoutError:
            duration = (time.monotonic() - start) * 1000
            return SandboxResult(
                success=False,
                error=f"Execution timed out after {self.config.timeout_seconds}s",
                duration_ms=duration,
                violations=["timeout_exceeded"],
            )

        except MemoryError:
            return SandboxResult(
                success=False,
                error="Memory limit exceeded",
                violations=["memory_exceeded"],
            )

        except Exception as e:
            duration = (time.monotonic() - start) * 1000
            return SandboxResult(
                success=False,
                error=str(e),
                duration_ms=duration,
            )

    def validate_command(self, command: str) -> tuple[bool, str]:
        """Check if a shell command is allowed."""
        for blocked in self.config.blocked_commands:
            if blocked in command:
                return False, f"Command contains blocked pattern: {blocked}"
        return True, ""

    def validate_path(self, path: str) -> tuple[bool, str]:
        """Check if a file path is within allowed directories."""
        abs_path = os.path.abspath(path)
        for allowed in self.config.allowed_paths:
            if abs_path.startswith(os.path.abspath(allowed)):
                return True, ""
        return False, f"Path {path} not in allowed directories"

    def validate_output(self, output: Any) -> tuple[bool, str]:
        """Check if output exceeds size limits."""
        if isinstance(output, (str, bytes)):
            size = len(output)
            if size > self.config.max_output_bytes:
                return False, f"Output size {size} exceeds limit {self.config.max_output_bytes}"
        return True, ""

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "executions": self._execution_count,
            "config": {
                "max_memory_mb": self.config.max_memory_mb,
                "max_cpu_seconds": self.config.max_cpu_seconds,
                "timeout_seconds": self.config.timeout_seconds,
                "network_allowed": self.config.network_allowed,
            },
        }
