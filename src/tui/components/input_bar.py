"""Input bar component — command entry with history."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Input, Label, Static


class InputBar(Static):
    """Command input bar with prompt and history navigation."""

    class CommandSubmitted(Message):
        def __init__(self, command: str) -> None:
            self.command = command
            super().__init__()

    def __init__(self, prompt: str = "▶ ", **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._prompt = prompt
        self._history: list[str] = []
        self._history_index: int = -1

    def compose(self) -> ComposeResult:
        yield Label(self._prompt, id="input-prompt")
        yield Input(placeholder="Enter command...", id="command-input")

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
        try:
            label = self.query_one("#input-prompt", Label)
            label.update(prompt)
        except Exception:
            pass

    def focus_input(self) -> None:
        """Focus the input field."""
        try:
            inp = self.query_one("#command-input", Input)
            inp.focus()
        except Exception:
            pass

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
