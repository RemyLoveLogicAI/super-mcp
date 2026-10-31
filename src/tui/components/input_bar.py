"""Input bar component — command entry with history."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.message import Message
from textual.widgets import Input, Label, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult


class InputBar(Static):
    """Command input bar with prompt and history navigation."""

    class CommandSubmitted(Message):
        def __init__(self, command: str) -> None:
            self.command = command
            super().__init__()

    def __init__(self, prompt: str = "▶ ", *, id: str | None = None) -> None:  # noqa: A002
        super().__init__(id=id)
        self._prompt = prompt
        self._history: list[str] = []
        self._history_index: int = -1

    def compose(self) -> ComposeResult:
        yield Label(self._prompt, id="input-prompt")
        yield Input(placeholder="Message the model, or /help for commands...", id="command-input")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command submission."""
        command = event.value.strip()
        if command:
            self._history.append(command)
            self._history_index = -1
            self.post_message(self.CommandSubmitted(command))
        event.input.value = ""

    def set_prompt(self, prompt: str) -> None:
        """Update the prompt text."""
        self._prompt = prompt
        if self.is_mounted:
            self.query_one("#input-prompt", Label).update(prompt)

    def focus_input(self) -> None:
        """Focus the input field."""
        if self.is_mounted:
            self.query_one("#command-input", Input).focus()

    DEFAULT_CSS = """
    InputBar {
        dock: bottom;
        height: 3;
        background: #1e293b;
        layout: horizontal;
        padding: 1 1;
    }

    #input-prompt {
        width: auto;
        color: #f59e0b;
        text-style: bold;
        padding-right: 1;
    }

    #command-input {
        width: 1fr;
        background: #0f172a;
        color: #f8fafc;
        border: none;
    }

    #command-input:focus {
        border: none;
    }
    """
