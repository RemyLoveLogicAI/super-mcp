"""Super-MCP Kernel — the central nervous system.

The kernel owns the lifecycle: boot → onboard → run → checkpoint → shutdown.
Everything else is a subsystem that registers with the kernel.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog

from src.kernel.event_bus import EventBus
from src.kernel.registry import CapabilityNegotiator, SkillRegistry, ToolRegistry
from src.kernel.safety import SafetyLayer
from src.kernel.types import (
    Artifact,
    ArtifactFormat,
    Checkpoint,
    Event,
    Session,
    SessionState,
    Severity,
)

logger = structlog.get_logger(__name__)


class Kernel:
    """The Super-MCP kernel. Owns registries, event bus, safety, and session."""

    def __init__(self) -> None:
        self.event_bus = EventBus(max_history=50_000)
        self.skill_registry = SkillRegistry(self.event_bus)
        self.tool_registry = ToolRegistry(self.event_bus)
        self.safety = SafetyLayer(self.event_bus)
        self.negotiator = CapabilityNegotiator(self.skill_registry, self.tool_registry)

        self._session: Session | None = None
        self._checkpoints: dict[UUID, Checkpoint] = {}
        self._artifacts: dict[UUID, Artifact] = {}
        self._checkpoint_sequence = 0
        self._booted = False

    async def boot(self) -> None:
        """Initialize the kernel and all subsystems."""
        if self._booted:
            return

        await self.event_bus.emit(
            kind="kernel.booting",
            source="kernel",
            severity=Severity.INFO,
        )

        self._session = Session(state=SessionState.INITIALIZING)

        await self.event_bus.emit(
            kind="kernel.booted",
            source="kernel",
            data={
                "session_id": str(self._session.id),
                "skills_loaded": self.skill_registry.count,
                "tools_loaded": self.tool_registry.count,
            },
        )
        self._booted = True

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        if self._session:
            self._session.state = SessionState.TERMINATED

        await self.event_bus.emit(
            kind="kernel.shutdown",
            source="kernel",
            severity=Severity.INFO,
        )
        self.event_bus.stop()
        self._booted = False

    @property
    def session(self) -> Session:
        if not self._session:
            raise RuntimeError("Kernel not booted. Call boot() first.")
        return self._session

    async def transition(self, new_state: SessionState) -> None:
        """Transition the session to a new state with event emission."""
        old_state = self.session.state
        self.session.state = new_state
        self.session.touch()

        await self.event_bus.emit(
            kind="session.state_changed",
            source="kernel",
            data={"old": old_state.value, "new": new_state.value},
        )

    async def checkpoint(self, state: dict[str, Any]) -> Checkpoint:
        """Create a deterministic checkpoint."""
        self._checkpoint_sequence += 1
        cp = Checkpoint(
            session_id=self.session.id,
            sequence=self._checkpoint_sequence,
            state=state,
        )
        cp.checksum = cp.compute_checksum()
        self._checkpoints[cp.id] = cp
        self.session.checkpoints.append(cp.id)

        await self.event_bus.emit(
            kind="checkpoint.created",
            source="kernel",
            data={
                "checkpoint_id": str(cp.id),
                "sequence": cp.sequence,
                "checksum": cp.checksum,
            },
        )
        return cp

    async def restore_checkpoint(self, checkpoint_id: UUID) -> Checkpoint | None:
        """Restore state from a checkpoint."""
        cp = self._checkpoints.get(checkpoint_id)
        if not cp:
            return None

        await self.event_bus.emit(
            kind="checkpoint.restored",
            source="kernel",
            data={
                "checkpoint_id": str(cp.id),
                "sequence": cp.sequence,
            },
        )
        return cp

    async def create_artifact(
        self,
        name: str,
        content: str | bytes,
        fmt: ArtifactFormat = ArtifactFormat.MARKDOWN,
        metadata: dict[str, Any] | None = None,
    ) -> Artifact:
        """Create and register an artifact."""
        artifact = Artifact(
            name=name,
            format=fmt,
            content=content,
            metadata=metadata or {},
            source_session=self.session.id,
        )
        self._artifacts[artifact.id.id] = artifact
        self.session.artifacts.append(artifact.id.id)

        await self.event_bus.emit(
            kind="artifact.created",
            source="kernel",
            data={
                "artifact_id": str(artifact.id.id),
                "name": name,
                "format": fmt.value,
            },
        )
        return artifact

    def get_artifact(self, artifact_id: UUID) -> Artifact | None:
        return self._artifacts.get(artifact_id)

    def list_artifacts(self) -> list[Artifact]:
        return list(self._artifacts.values())

    async def execute_with_safety(
        self,
        action_description: str,
        action_fn: Any,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Run an action through the safety layer first."""
        evaluation = await self.safety.evaluate(action_description, context)

        if not evaluation.allowed:
            await self.event_bus.emit(
                kind="action.blocked",
                source="kernel",
                data={
                    "action": action_description,
                    "verdict": evaluation.verdict.value,
                    "rules": [r.id for r in evaluation.triggered_rules],
                },
                severity=Severity.WARN,
            )
            return evaluation

        if evaluation.warnings:
            for warning in evaluation.warnings:
                await logger.awarn("safety_warning", warning=warning)

        result = await action_fn()

        await self.event_bus.emit(
            kind="action.completed",
            source="kernel",
            data={"action": action_description},
        )
        return result

    @property
    def status(self) -> dict[str, Any]:
        return {
            "booted": self._booted,
            "session_id": str(self.session.id) if self._session else None,
            "session_state": self.session.state.value if self._session else None,
            "skills_registered": self.skill_registry.count,
            "tools_registered": self.tool_registry.count,
            "checkpoints": len(self._checkpoints),
            "artifacts": len(self._artifacts),
            "events_total": self.event_bus.event_count,
            "safety_stats": self.safety.stats,
        }
