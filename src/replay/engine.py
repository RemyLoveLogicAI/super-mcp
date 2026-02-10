"""Replay Engine — deterministic event replay and session rewind.

Provides full session replay from event history, checkpoint-based
rewind, and exportable replay bundles for debugging and analysis.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog

from src.kernel.event_bus import EventBus
from src.kernel.types import Checkpoint, Event, Severity

logger = structlog.get_logger(__name__)


@dataclass
class ReplayFrame:
    """Single frame in a replay sequence."""
    sequence: int
    event: Event
    state_delta: dict[str, Any] = field(default_factory=dict)
    annotations: list[str] = field(default_factory=list)


@dataclass
class ReplayBundle:
    """Exportable replay package."""
    session_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now())
    frames: list[ReplayFrame] = field(default_factory=list)
    checkpoints: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "frame_count": len(self.frames),
            "checkpoint_count": len(self.checkpoints),
            "metadata": self.metadata,
            "frames": [
                {
                    "sequence": f.sequence,
                    "event": {
                        "kind": f.event.kind,
                        "source": f.event.source,
                        "severity": f.event.severity.value,
                        "timestamp": f.event.timestamp.isoformat(),
                        "data": f.event.data,
                    },
                    "state_delta": f.state_delta,
                    "annotations": f.annotations,
                }
                for f in self.frames
            ],
            "checkpoints": self.checkpoints,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


class ReplayEngine:
    """Deterministic replay from event history."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._recording = False
        self._frames: list[ReplayFrame] = []
        self._sequence = 0

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    async def start_recording(self) -> None:
        """Start capturing events for replay."""
        self._recording = True
        self._frames = []
        self._sequence = 0
        self._event_bus.subscribe_all(self._capture_event)
        await logger.ainfo("replay_recording_started")

    async def stop_recording(self) -> None:
        """Stop capturing events."""
        self._recording = False
        await logger.ainfo("replay_recording_stopped", frames=len(self._frames))

    async def _capture_event(self, event: Event) -> None:
        """Capture event into replay buffer."""
        if not self._recording:
            return
        self._sequence += 1
        frame = ReplayFrame(sequence=self._sequence, event=event)
        self._frames.append(frame)

    def build_bundle(
        self,
        session_id: str,
        checkpoints: list[Checkpoint] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ReplayBundle:
        """Build an exportable replay bundle."""
        cp_dicts = []
        if checkpoints:
            for cp in checkpoints:
                cp_dicts.append({
                    "id": str(cp.id),
                    "sequence": cp.sequence,
                    "checksum": cp.checksum,
                    "state": cp.state,
                    "created_at": cp.created_at.isoformat(),
                })

        return ReplayBundle(
            session_id=session_id,
            frames=list(self._frames),
            checkpoints=cp_dicts,
            metadata=metadata or {},
        )

    async def export_bundle(self, bundle: ReplayBundle, output_path: Path) -> Path:
        """Export replay bundle to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(bundle.to_json(), encoding="utf-8")
        await logger.ainfo("replay_exported", path=str(output_path), frames=len(bundle.frames))
        return output_path

    async def load_bundle(self, path: Path) -> ReplayBundle:
        """Load a replay bundle from file."""
        data = json.loads(path.read_text(encoding="utf-8"))
        frames = []
        for fd in data.get("frames", []):
            ev = Event(
                kind=fd["event"]["kind"],
                source=fd["event"]["source"],
                severity=Severity(fd["event"]["severity"]),
                data=fd["event"].get("data", {}),
            )
            frames.append(ReplayFrame(
                sequence=fd["sequence"],
                event=ev,
                state_delta=fd.get("state_delta", {}),
                annotations=fd.get("annotations", []),
            ))

        return ReplayBundle(
            session_id=data["session_id"],
            frames=frames,
            checkpoints=data.get("checkpoints", []),
            metadata=data.get("metadata", {}),
        )

    async def replay(
        self,
        bundle: ReplayBundle,
        speed: float = 1.0,
        callback: Any = None,
    ) -> None:
        """Replay events from a bundle, optionally invoking callback per frame."""
        await logger.ainfo("replay_started", frames=len(bundle.frames), speed=speed)

        for i, frame in enumerate(bundle.frames):
            if callback:
                await callback(frame, i, len(bundle.frames))

            # Emit replayed event
            await self._event_bus.emit(
                kind=f"replay.{frame.event.kind}",
                source="replay_engine",
                data={
                    "original_source": frame.event.source,
                    "original_data": frame.event.data,
                    "frame": frame.sequence,
                },
            )

        await logger.ainfo("replay_complete", frames=len(bundle.frames))

    def get_frames_between(
        self,
        start_seq: int = 0,
        end_seq: int | None = None,
    ) -> list[ReplayFrame]:
        """Get frames in a sequence range."""
        return [
            f for f in self._frames
            if f.sequence >= start_seq and (end_seq is None or f.sequence <= end_seq)
        ]

    def annotate_frame(self, sequence: int, note: str) -> bool:
        """Add an annotation to a specific frame."""
        for frame in self._frames:
            if frame.sequence == sequence:
                frame.annotations.append(note)
                return True
        return False
