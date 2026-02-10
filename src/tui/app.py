"""Super-MCP TUI Application — Textual-based keyboard-first interface.

The TUI is the primary interaction surface: modular panes, live logs,
status indicators, skill/tool browsers, game launcher, and full
keyboard navigation.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header

from src.games.adventure.game import AdventureGame
from src.games.dnd.game import DnDGame
from src.games.engine.runner import GameRunner
from src.games.engine.state import GameStateManager
from src.games.zork.game import ZorkGame
from src.kernel.kernel import Kernel
from src.kernel.types import SessionState, Severity
from src.tui.components.event_log import EventLog
from src.tui.components.header import HeaderBar
from src.tui.components.input_bar import InputBar
from src.tui.components.output_pane import OutputPane
from src.tui.components.sidebar import Sidebar
from src.tui.components.status_bar import StatusBar


class SuperMCPApp(App):
    """The Super-MCP Terminal User Interface."""

    TITLE = "Super-MCP"
    SUB_TITLE = "Universal Model Context Protocol Platform"

    CSS = """
    Screen {
        background: #0f172a;
    }

    #main-layout {
        layout: horizontal;
        height: 1fr;
    }

    #content-column {
        width: 1fr;
        layout: vertical;
    }

    #sidebar-toggle {
        display: block;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("f1", "show_help", "Help", show=True),
        Binding("f2", "focus_tab('tab-skills')", "Skills", show=True),
        Binding("f3", "focus_tab('tab-tools')", "Tools", show=True),
        Binding("f4", "focus_tab('tab-games')", "Games", show=True),
        Binding("f5", "toggle_events", "Events", show=True),
        Binding("ctrl+l", "clear_output", "Clear", show=False),
        Binding("ctrl+s", "toggle_sidebar", "Sidebar", show=False),
        Binding("escape", "focus_input", "Input", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.kernel = Kernel()
        self.game_runner = GameRunner()
        self._sidebar_visible = True
        self._events_visible = True
        self._current_mode = "COMMAND"  # COMMAND, GAME, ONBOARDING
        self._active_game: str | None = None

    def compose(self) -> ComposeResult:
        yield HeaderBar()
        with Horizontal(id="main-layout"):
            yield Sidebar(id="sidebar-toggle")
            with Vertical(id="content-column"):
                yield OutputPane()
                yield EventLog()
        yield InputBar()
        yield StatusBar()

    async def on_mount(self) -> None:
        """Boot kernel and register event listeners."""
        # Register games
        self.game_runner.register_game("dnd", DnDGame())
        self.game_runner.register_game("adventure", AdventureGame())
        self.game_runner.register_game("zork", ZorkGame())

        # Subscribe to kernel events for the live log
        self.kernel.event_bus.subscribe_all(self._on_kernel_event)

        # Boot kernel
        await self.kernel.boot()
        await self.kernel.transition(SessionState.READY)

        # Update header
        header = self.query_one(HeaderBar)
        header.session_state = "READY"
        header.skill_count = self.kernel.skill_registry.count
        header.tool_count = self.kernel.tool_registry.count

        # Welcome message
        output = self.query_one(OutputPane)
        output.write_system(
            "═══════════════════════════════════════════════════════════\n"
            "  ⚡ SUPER-MCP — Universal Model Context Protocol Platform\n"
            "═══════════════════════════════════════════════════════════\n"
        )
        output.write_system(
            f"Kernel booted. Session: {self.kernel.session.id}\n"
            f"Skills: {self.kernel.skill_registry.count}  "
            f"Tools: {self.kernel.tool_registry.count}\n"
        )
        output.write_system(
            "Commands:\n"
            "  /skills          — List all registered skills\n"
            "  /tools           — List all registered tools\n"
            "  /status          — Show kernel status\n"
            "  /onboard         — Run onboarding wizard\n"
            "  /game <type>     — Launch a game (dnd, adventure, zork)\n"
            "  /game quit       — Exit current game\n"
            "  /checkpoint      — Create a checkpoint\n"
            "  /events          — Show recent events\n"
            "  /clear           — Clear output\n"
            "  /help            — Show this help\n"
        )

        # Focus input
        input_bar = self.query_one(InputBar)
        input_bar.focus_input()

    async def _on_kernel_event(self, event: Any) -> None:
        """Forward kernel events to the event log."""
        try:
            event_log = self.query_one(EventLog)
            event_log.append_event(
                kind=event.kind,
                source=event.source,
                severity=event.severity.value if hasattr(event.severity, "value") else str(event.severity),
                data=event.data,
                timestamp=event.timestamp,
            )
        except Exception:
            pass

    # ── Command handling ─────────────────────────────────────────

    async def on_input_bar_command_submitted(self, event: InputBar.CommandSubmitted) -> None:
        """Route commands from the input bar."""
        command = event.command.strip()
        output = self.query_one(OutputPane)

        # Echo input
        output.write(f"[bold yellow]▶[/bold yellow] {command}")

        if self._active_game and not command.startswith("/"):
            # Forward to game
            await self._handle_game_input(command)
        elif command.startswith("/"):
            await self._handle_system_command(command)
        else:
            output.write_system("Unknown command. Type /help for available commands.")

        # Refocus input
        input_bar = self.query_one(InputBar)
        input_bar.focus_input()

    async def _handle_system_command(self, command: str) -> None:
        """Handle /commands."""
        output = self.query_one(OutputPane)
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "/help":
            await self._cmd_help()
        elif cmd == "/status":
            await self._cmd_status()
        elif cmd == "/skills":
            await self._cmd_skills(args)
        elif cmd == "/tools":
            await self._cmd_tools(args)
        elif cmd == "/game":
            await self._cmd_game(args)
        elif cmd == "/onboard":
            await self._cmd_onboard()
        elif cmd == "/checkpoint":
            await self._cmd_checkpoint()
        elif cmd == "/events":
            await self._cmd_events()
        elif cmd == "/clear":
            output.clear()
        elif cmd == "/quit":
            if self._active_game:
                self._active_game = None
                self._current_mode = "COMMAND"
                status = self.query_one(StatusBar)
                status.mode = "COMMAND"
                status.health_text = ""
                input_bar = self.query_one(InputBar)
                input_bar.set_prompt("▶ ")
                output.write_system("Game ended. Returned to command mode.")
            else:
                self.exit()
        else:
            output.write_system(f"Unknown command: {cmd}")

    async def _cmd_help(self) -> None:
        output = self.query_one(OutputPane)
        output.write_system(
            "═══ Super-MCP Commands ═══\n"
            "  /skills [filter]    — Browse skills\n"
            "  /tools [filter]     — Browse tools\n"
            "  /status             — Kernel status\n"
            "  /onboard            — Run onboarding\n"
            "  /game dnd           — Launch D&D Quest\n"
            "  /game adventure     — Launch Adventure\n"
            "  /game zork          — Launch Ruins of Zyl\n"
            "  /game quit          — Exit game\n"
            "  /checkpoint         — Save checkpoint\n"
            "  /events             — Recent events\n"
            "  /clear              — Clear output\n"
            "  /quit               — Quit\n"
            "\nKeyboard:\n"
            "  F1: Help  F2: Skills  F3: Tools  F4: Games\n"
            "  F5: Toggle Events  Ctrl+S: Toggle Sidebar\n"
            "  Ctrl+L: Clear  Ctrl+Q: Quit  Esc: Focus Input"
        )

    async def _cmd_status(self) -> None:
        output = self.query_one(OutputPane)
        status = self.kernel.status
        output.write_system(
            "═══ Kernel Status ═══\n"
            f"  Booted:      {status['booted']}\n"
            f"  Session:     {status['session_id']}\n"
            f"  State:       {status['session_state']}\n"
            f"  Skills:      {status['skills_registered']}\n"
            f"  Tools:       {status['tools_registered']}\n"
            f"  Checkpoints: {status['checkpoints']}\n"
            f"  Artifacts:   {status['artifacts']}\n"
            f"  Events:      {status['events_total']}\n"
            f"  Safety:      {status['safety_stats']}"
        )

    async def _cmd_skills(self, filter_text: str = "") -> None:
        output = self.query_one(OutputPane)
        skills = self.kernel.skill_registry.list_all()
        if filter_text:
            skills = [s for s in skills if filter_text.lower() in s.name.lower()
                      or filter_text.lower() in s.slug]

        if not skills:
            output.write_system("No skills found matching filter.")
            return

        output.write_system(f"═══ Skills ({len(skills)}) ═══")
        for skill in skills[:50]:  # Show first 50
            output.write(f"  [{skill.category.value:>12}] {skill.slug:<30} {skill.name}")

        if len(skills) > 50:
            output.write_system(f"  ... and {len(skills) - 50} more. Use /skills <filter> to narrow.")

    async def _cmd_tools(self, filter_text: str = "") -> None:
        output = self.query_one(OutputPane)
        tools = self.kernel.tool_registry.list_all()
        if filter_text:
            tools = [t for t in tools if filter_text.lower() in t.name.lower()
                     or filter_text.lower() in t.slug]

        if not tools:
            output.write_system("No tools found matching filter.")
            return

        output.write_system(f"═══ Tools ({len(tools)}) ═══")
        for tool in tools[:50]:
            health_icon = {"healthy": "●", "degraded": "◐", "down": "○"}.get(
                tool.health.value if hasattr(tool.health, "value") else "unknown", "?"
            )
            output.write(f"  {health_icon} {tool.slug:<25} {tool.name}")

    async def _cmd_game(self, args: str) -> None:
        output = self.query_one(OutputPane)
        status = self.query_one(StatusBar)

        if args == "quit" or args == "exit":
            if self._active_game:
                self._active_game = None
                self._current_mode = "COMMAND"
                status.mode = "COMMAND"
                status.health_text = ""
                input_bar = self.query_one(InputBar)
                input_bar.set_prompt("▶ ")
                output.write_system("Game ended.")
            else:
                output.write_system("No game is running.")
            return

        if not args:
            output.write_system(
                "Available games:\n"
                "  /game dnd       — AI D&D Quest Engine\n"
                "  /game adventure — Choose Your Own Adventure\n"
                "  /game zork      — The Ruins of Zyl (Interactive Fiction)"
            )
            return

        game_type = args.strip().lower()
        if game_type not in self.game_runner._games:
            output.write_error(f"Unknown game: {game_type}")
            return

        # Launch game
        self._active_game = game_type
        self._current_mode = "GAME"
        status.mode = "GAME"

        game = self.game_runner._games[game_type]
        try:
            intro = await game.initialize()
            output.write_game(intro)

            input_bar = self.query_one(InputBar)
            input_bar.set_prompt("game▶ ")

            await self.kernel.event_bus.emit(
                kind="game.launched",
                source="tui",
                data={"game_type": game_type},
            )
        except Exception as e:
            output.write_error(f"Failed to start game: {e}")
            self._active_game = None
            self._current_mode = "COMMAND"
            status.mode = "COMMAND"

    async def _handle_game_input(self, user_input: str) -> None:
        """Forward input to the active game."""
        output = self.query_one(OutputPane)

        if not self._active_game:
            return

        game = self.game_runner._games.get(self._active_game)
        if not game:
            return

        try:
            response = await game.process_input(user_input)
            output.write_game(response)

            # Update health in status bar for games that have it
            if hasattr(game, "health") and hasattr(game, "max_health"):
                status = self.query_one(StatusBar)
                status.health_text = f"HP: {game.health}/{game.max_health}"

        except Exception as e:
            output.write_error(f"Game error: {e}")

    async def _cmd_onboard(self) -> None:
        output = self.query_one(OutputPane)
        status = self.query_one(StatusBar)
        status.mode = "ONBOARDING"

        output.write_system("Starting onboarding...")

        try:
            from src.onboarding.engine import OnboardingEngine

            engine = OnboardingEngine(self.kernel)
            report = await engine.run()

            output.write_system("═══ Onboarding Report ═══")
            for step in report.steps:
                icon = "✓" if step.success else "✗"
                color = "green" if step.success else "red"
                output.write(f"  [{color}]{icon}[/{color}] {step.step_name} ({step.duration_ms:.0f}ms)")
                if step.warnings:
                    for w in step.warnings:
                        output.write(f"    [yellow]⚠ {w}[/yellow]")

            output.write_system(
                f"\nTotal: {report.total_duration_ms:.0f}ms  "
                f"Success: {sum(1 for s in report.steps if s.success)}/{len(report.steps)}"
            )

            # Update header counts
            header = self.query_one(HeaderBar)
            header.skill_count = self.kernel.skill_registry.count
            header.tool_count = self.kernel.tool_registry.count
            header.session_state = self.kernel.session.state.value

        except Exception as e:
            output.write_error(f"Onboarding failed: {e}")

        status.mode = "COMMAND"

    async def _cmd_checkpoint(self) -> None:
        output = self.query_one(OutputPane)
        state = {"mode": self._current_mode, "active_game": self._active_game}
        cp = await self.kernel.checkpoint(state)
        output.write_success(
            f"Checkpoint created: {cp.id}\n"
            f"  Sequence: {cp.sequence}  Checksum: {cp.checksum}"
        )

    async def _cmd_events(self) -> None:
        output = self.query_one(OutputPane)
        events = self.kernel.event_bus.history(limit=20)
        output.write_system(f"═══ Recent Events ({len(events)}) ═══")
        for ev in events:
            ts = ev.timestamp.strftime("%H:%M:%S")
            output.write(f"  [{ts}] {ev.severity.value:>5} [{ev.source}] {ev.kind}")

    # ── Actions ──────────────────────────────────────────────────

    def action_show_help(self) -> None:
        asyncio.create_task(self._cmd_help())

    def action_focus_tab(self, tab_id: str) -> None:
        try:
            from textual.widgets import TabbedContent
            tabs = self.query_one("#sidebar-tabs", TabbedContent)
            tabs.active = tab_id
        except Exception:
            pass

    def action_toggle_events(self) -> None:
        event_log = self.query_one(EventLog)
        self._events_visible = not self._events_visible
        event_log.display = self._events_visible

    def action_toggle_sidebar(self) -> None:
        sidebar = self.query_one("#sidebar-toggle")
        self._sidebar_visible = not self._sidebar_visible
        sidebar.display = self._sidebar_visible

    def action_clear_output(self) -> None:
        output = self.query_one(OutputPane)
        output.clear()

    def action_focus_input(self) -> None:
        input_bar = self.query_one(InputBar)
        input_bar.focus_input()


def run_tui() -> None:
    """Entry point for the TUI."""
    app = SuperMCPApp()
    app.run()
