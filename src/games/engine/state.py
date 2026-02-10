"""Game state management — deterministic checkpoints and replay.

Every game action produces a state transition. The state is
serializable, checkpointable, and replayable from any point.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any
from uuid import UUID, uuid4


class GamePhase(str, Enum):
    SETUP = "setup"
    CHARACTER_CREATION = "character_creation"
    PLAYING = "playing"
    COMBAT = "combat"
    PAUSED = "paused"
    COMPLETED = "completed"
    GAME_OVER = "game_over"


@dataclass
class GameAction:
    """A single player or system action in the game."""
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    timestamp: float = field(default_factory=time.time)
    actor: str = "player"  # "player" | "system" | "dm"
    action_type: str = ""  # "move", "examine", "attack", "choose", etc.
    action_data: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    result: str = ""
    valid: bool = True
    rollback_data: dict[str, Any] | None = None


@dataclass
class GameState:
    """Complete serializable game state."""
    game_id: str = field(default_factory=lambda: str(uuid4()))
    game_type: str = ""
    phase: GamePhase = GamePhase.SETUP
    turn_number: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # World state
    world: dict[str, Any] = field(default_factory=dict)
    player: dict[str, Any] = field(default_factory=dict)
    npcs: dict[str, Any] = field(default_factory=dict)
    inventory: list[str] = field(default_factory=list)
    quest_log: list[dict[str, Any]] = field(default_factory=list)
    flags: dict[str, bool] = field(default_factory=dict)

    # Action history
    actions: list[GameAction] = field(default_factory=list)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "game_type": self.game_type,
            "phase": self.phase.value,
            "turn_number": self.turn_number,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "world": self.world,
            "player": self.player,
            "npcs": self.npcs,
            "inventory": list(self.inventory),
            "quest_log": list(self.quest_log),
            "flags": dict(self.flags),
            "actions": [
                {
                    "id": a.id,
                    "timestamp": a.timestamp,
                    "actor": a.actor,
                    "action_type": a.action_type,
                    "description": a.description,
                    "result": a.result,
                    "valid": a.valid,
                }
                for a in self.actions
            ],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameState:
        state = cls(
            game_id=data["game_id"],
            game_type=data.get("game_type", ""),
            phase=GamePhase(data.get("phase", "setup")),
            turn_number=data.get("turn_number", 0),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            world=data.get("world", {}),
            player=data.get("player", {}),
            npcs=data.get("npcs", {}),
            inventory=data.get("inventory", []),
            quest_log=data.get("quest_log", []),
            flags=data.get("flags", {}),
            metadata=data.get("metadata", {}),
        )
        for a in data.get("actions", []):
            state.actions.append(GameAction(
                id=a.get("id", ""),
                timestamp=a.get("timestamp", 0),
                actor=a.get("actor", "player"),
                action_type=a.get("action_type", ""),
                description=a.get("description", ""),
                result=a.get("result", ""),
                valid=a.get("valid", True),
            ))
        return state

    def checksum(self) -> str:
        """Deterministic checksum of the game state (excluding action history)."""
        import json
        core = json.dumps({
            "world": self.world,
            "player": self.player,
            "inventory": sorted(self.inventory),
            "flags": dict(sorted(self.flags.items())),
            "turn": self.turn_number,
        }, sort_keys=True)
        return hashlib.sha256(core.encode()).hexdigest()[:16]


@dataclass
class GameCheckpoint:
    """Save slot for game state."""
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    name: str = ""
    state: GameState | None = None
    created_at: float = field(default_factory=time.time)
    checksum: str = ""

    def validate(self) -> bool:
        if not self.state:
            return False
        return self.state.checksum() == self.checksum


class GameStateManager:
    """Manages game state with undo, redo, checkpoints, and replay."""

    def __init__(self, max_undo: int = 100) -> None:
        self._state: GameState | None = None
        self._undo_stack: list[dict[str, Any]] = []
        self._redo_stack: list[dict[str, Any]] = []
        self._checkpoints: dict[str, GameCheckpoint] = {}
        self._max_undo = max_undo

    @property
    def state(self) -> GameState:
        if not self._state:
            raise RuntimeError("No active game state")
        return self._state

    def new_game(self, game_type: str) -> GameState:
        self._state = GameState(game_type=game_type)
        self._undo_stack.clear()
        self._redo_stack.clear()
        return self._state

    def apply_action(self, action: GameAction) -> None:
        """Apply an action, pushing current state to undo stack."""
        if not self._state:
            raise RuntimeError("No active game")

        # Save current state for undo
        snapshot = self._state.to_dict()
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)

        # Clear redo stack on new action
        self._redo_stack.clear()

        # Apply action
        self._state.actions.append(action)
        self._state.turn_number += 1
        self._state.updated_at = time.time()

    def undo(self) -> bool:
        """Undo the last action."""
        if not self._undo_stack:
            return False

        # Save current state for redo
        if self._state:
            self._redo_stack.append(self._state.to_dict())

        # Restore previous state
        prev = self._undo_stack.pop()
        self._state = GameState.from_dict(prev)
        return True

    def redo(self) -> bool:
        """Redo a previously undone action."""
        if not self._redo_stack:
            return False

        if self._state:
            self._undo_stack.append(self._state.to_dict())

        next_state = self._redo_stack.pop()
        self._state = GameState.from_dict(next_state)
        return True

    def save_checkpoint(self, name: str = "") -> GameCheckpoint:
        """Create a named save point."""
        if not self._state:
            raise RuntimeError("No active game")

        cp = GameCheckpoint(
            name=name or f"save-{len(self._checkpoints) + 1}",
            state=GameState.from_dict(self._state.to_dict()),  # deep copy
            checksum=self._state.checksum(),
        )
        self._checkpoints[cp.id] = cp
        return cp

    def load_checkpoint(self, checkpoint_id: str) -> bool:
        """Restore from a checkpoint."""
        cp = self._checkpoints.get(checkpoint_id)
        if not cp or not cp.state:
            return False

        self._undo_stack.append(self._state.to_dict() if self._state else {})
        self._state = GameState.from_dict(cp.state.to_dict())
        return True

    def list_checkpoints(self) -> list[GameCheckpoint]:
        return list(self._checkpoints.values())

    def replay_from_start(self) -> list[GameAction]:
        """Return all actions for replay."""
        if not self._state:
            return []
        return list(self._state.actions)

    def replay_from_checkpoint(self, checkpoint_id: str) -> list[GameAction]:
        """Return actions since a checkpoint."""
        cp = self._checkpoints.get(checkpoint_id)
        if not cp or not cp.state or not self._state:
            return []

        cp_turn = cp.state.turn_number
        return [a for i, a in enumerate(self._state.actions) if i >= cp_turn]
