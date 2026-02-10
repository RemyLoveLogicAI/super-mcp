"""Game runner — unified interface for all game types.

Handles game lifecycle, input parsing, and output formatting.
Games plug in via the GameInterface protocol.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.games.engine.state import (
    GameAction,
    GameCheckpoint,
    GamePhase,
    GameState,
    GameStateManager,
)
from src.kernel.event_bus import EventBus
from src.kernel.types import Artifact, ArtifactFormat


@dataclass
class GameOutput:
    """Structured output from a game turn."""
    narrative: str = ""
    options: list[str] = field(default_factory=list)
    prompt: str = "> "
    state_summary: str = ""
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    game_over: bool = False
    error: str | None = None


class GameInterface(ABC):
    """Protocol that all games must implement."""

    @abstractmethod
    def game_type(self) -> str: ...

    @abstractmethod
    async def initialize(self, state: GameState) -> GameOutput: ...

    @abstractmethod
    async def process_input(self, user_input: str, state: GameState) -> tuple[GameOutput, GameAction]: ...

    @abstractmethod
    async def get_help(self) -> str: ...

    @abstractmethod
    def validate_input(self, user_input: str, state: GameState) -> tuple[bool, str]: ...

    @abstractmethod
    async def generate_summary(self, state: GameState) -> str: ...


class GameRunner:
    """Orchestrates game sessions with any GameInterface implementation."""

    def __init__(self, event_bus: EventBus) -> None:
        self._bus = event_bus
        self._games: dict[str, GameInterface] = {}
        self._active: dict[str, tuple[GameInterface, GameStateManager]] = {}

    def register_game(self, game: GameInterface) -> None:
        self._games[game.game_type()] = game

    def available_games(self) -> list[str]:
        return list(self._games.keys())

    async def start_game(self, game_type: str) -> tuple[str, GameOutput]:
        """Start a new game session. Returns (game_id, initial_output)."""
        game = self._games.get(game_type)
        if not game:
            return "", GameOutput(error=f"Unknown game type: {game_type}")

        manager = GameStateManager()
        state = manager.new_game(game_type)
        game_id = state.game_id

        self._active[game_id] = (game, manager)

        output = await game.initialize(state)

        await self._bus.emit(
            kind="game.started",
            source="game_runner",
            data={"game_id": game_id, "game_type": game_type},
        )

        return game_id, output

    async def process_turn(self, game_id: str, user_input: str) -> GameOutput:
        """Process a player turn."""
        if game_id not in self._active:
            return GameOutput(error="Game not found")

        game, manager = self._active[game_id]
        state = manager.state

        # Handle meta-commands
        cmd = user_input.strip().lower()
        if cmd == "/help":
            return GameOutput(narrative=await game.get_help())
        if cmd == "/save":
            cp = manager.save_checkpoint()
            return GameOutput(narrative=f"Game saved: {cp.name} (ID: {cp.id})")
        if cmd == "/load":
            checkpoints = manager.list_checkpoints()
            if not checkpoints:
                return GameOutput(narrative="No save points available.")
            listing = "\n".join(f"  [{cp.id}] {cp.name}" for cp in checkpoints)
            return GameOutput(narrative=f"Available saves:\n{listing}\n\nUse /load <id> to restore.")
        if cmd.startswith("/load "):
            cp_id = cmd.split(" ", 1)[1].strip()
            if manager.load_checkpoint(cp_id):
                return GameOutput(narrative=f"Loaded save point: {cp_id}")
            return GameOutput(narrative=f"Save point not found: {cp_id}")
        if cmd == "/undo":
            if manager.undo():
                return GameOutput(narrative="Undone. You are back to the previous state.")
            return GameOutput(narrative="Nothing to undo.")
        if cmd == "/redo":
            if manager.redo():
                return GameOutput(narrative="Redone.")
            return GameOutput(narrative="Nothing to redo.")
        if cmd == "/status":
            summary = await game.generate_summary(state)
            return GameOutput(narrative=summary, state_summary=summary)
        if cmd == "/quit":
            summary = await game.generate_summary(state)
            del self._active[game_id]
            await self._bus.emit(
                kind="game.ended",
                source="game_runner",
                data={"game_id": game_id},
            )
            return GameOutput(narrative=f"Game ended.\n\n{summary}", game_over=True)
        if cmd == "/replay":
            actions = manager.replay_from_start()
            lines = [f"Turn {i+1}: [{a.actor}] {a.description}" for i, a in enumerate(actions)]
            return GameOutput(narrative="=== Replay ===\n" + "\n".join(lines))

        # Validate input
        valid, error_msg = game.validate_input(user_input, state)
        if not valid:
            return GameOutput(narrative=error_msg, error=error_msg)

        # Process the turn
        output, action = await game.process_input(user_input, state)
        manager.apply_action(action)

        await self._bus.emit(
            kind="game.turn",
            source="game_runner",
            data={
                "game_id": game_id,
                "turn": state.turn_number,
                "action": action.action_type,
            },
        )

        if output.game_over:
            await self._bus.emit(
                kind="game.completed",
                source="game_runner",
                data={"game_id": game_id, "turns": state.turn_number},
            )

        return output

    async def get_state(self, game_id: str) -> GameState | None:
        if game_id in self._active:
            return self._active[game_id][1].state
        return None

    def active_games(self) -> list[str]:
        return list(self._active.keys())
