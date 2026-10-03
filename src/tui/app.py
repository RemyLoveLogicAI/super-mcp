"""Super-MCP TUI Application — Textual-based keyboard-first interface.

The TUI is the primary interaction surface: modular panes, live logs,
status indicators, skill/tool browsers, game launcher, full keyboard
navigation, and a streaming chat with any configured model provider.

Free text goes to the model (or to the active game); ``/commands`` drive
the platform. Esc cancels a response that is still streaming.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from rich.markup import escape
from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import TabbedContent

from src.games.adventure.game import AdventureGame
from src.games.dnd.game import DnDGame
from src.games.engine.runner import GameOutput, GameRunner
from src.games.zork.game import ZorkGame
from src.kernel.kernel import Kernel
from src.kernel.types import SessionState, Severity
from src.tui.components.event_log import EventLog
from src.tui.components.header import HeaderBar
from src.tui.components.input_bar import InputBar
from src.tui.components.output_pane import OutputPane
from src.tui.components.sidebar import Sidebar
from src.tui.components.status_bar import StatusBar

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.worker import Worker

    from src.harness.errors import HarnessError
    from src.harness.session import ChatSession
    from src.harness.types import Usage
    from src.kernel.types import Event


class SuperMCPApp(App[None]):
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

    BINDINGS = [  # noqa: RUF012 - Textual class-level declaration
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("f1", "show_help", "Help", show=True),
        Binding("f2", "focus_tab('tab-skills')", "Skills", show=True),
        Binding("f3", "focus_tab('tab-tools')", "Tools", show=True),
        Binding("f4", "focus_tab('tab-games')", "Games", show=True),
        Binding("f5", "toggle_events", "Events", show=True),
        Binding("ctrl+l", "clear_output", "Clear", show=False),
        Binding("ctrl+s", "toggle_sidebar", "Sidebar", show=False),
        Binding("escape", "cancel_or_focus", "Cancel/Input", show=False, priority=True),
    ]

    def __init__(
        self,
        *,
        chat: ChatSession | None = None,
        chat_unavailable: str | None = None,
        initial_prompt: str | None = None,
    ) -> None:
        super().__init__()
        self.kernel = Kernel()
        self.game_runner = GameRunner(self.kernel.event_bus)
        self.chat = chat
        self._chat_unavailable = chat_unavailable
        self._initial_prompt = initial_prompt
        self._chat_worker: Worker[None] | None = None
        self._sidebar_visible = True
        self._events_visible = True
        self._ui_mode = "COMMAND"  # COMMAND, GAME, ONBOARDING, STREAMING
        self._active_game: str | None = None
        self._active_game_id: str | None = None
        if chat is not None:
            chat.provider.on_retry = self._on_provider_retry

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
        self.kernel.event_bus.subscribe_all(self._on_kernel_event)
        await self._register_games()

        await self.kernel.boot()
        await self.kernel.transition(SessionState.READY)

        header = self.query_one(HeaderBar)
        header.session_state = "READY"
        header.skill_count = self.kernel.skill_registry.count
        header.tool_count = self.kernel.tool_registry.count

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
        self._describe_chat(output)
        output.write_system("Type a message to chat, or /help for commands.")
        self._refresh_status()

        self.query_one(InputBar).focus_input()
        if self._initial_prompt and self.chat is not None:
            self._start_chat(self._initial_prompt)

    async def _register_games(self) -> None:
        """Register each game independently so one broken game cannot block the TUI."""
        for factory in (DnDGame, AdventureGame, ZorkGame):
            try:
                self.game_runner.register_game(factory())
            except Exception as exc:  # noqa: BLE001 - report and continue
                await self.kernel.event_bus.emit(
                    "game.unavailable",
                    "tui",
                    {"game": factory.__name__, "error": f"{type(exc).__name__}: {exc}"},
                    severity=Severity.WARN,
                )

    async def on_unmount(self) -> None:
        """Stop any in-flight response and release the provider's connections."""
        if self._chat_worker is not None and not self._chat_worker.is_finished:
            self._chat_worker.cancel()
        if self.chat is not None:
            await self.chat.provider.aclose()

    def _describe_chat(self, output: OutputPane) -> None:
        if self.chat is not None:
            p = self.chat.provider
            output.write_system(
                f"Model: {escape(p.name)} · {escape(p.model or '(no model set)')} "
                f"@ {escape(p.endpoint)}"
            )
        else:
            output.write_error(
                f"Chat disabled: {self._chat_unavailable or 'no provider configured'}"
            )

    async def _on_kernel_event(self, event: Event) -> None:
        """Forward kernel events to the event log."""
        if not self.is_running:
            return
        self.query_one(EventLog).append_event(
            kind=event.kind,
            source=event.source,
            severity=event.severity.value,
            data=event.data,
            timestamp=event.timestamp,
        )

    # ── Command handling ─────────────────────────────────────────

    async def on_input_bar_command_submitted(self, event: InputBar.CommandSubmitted) -> None:
        """Route commands from the input bar."""
        command = event.command.strip()
        output = self.query_one(OutputPane)
        output.write(f"[bold yellow]▶[/bold yellow] {escape(command)}")

        if self._active_game and (not command.startswith("/") or _is_game_meta(command)):
            await self._handle_game_input(command)
        elif command.startswith("/"):
            await self._handle_system_command(command)
        else:
            self._start_chat(command)

        self.query_one(InputBar).focus_input()

    async def _handle_system_command(self, command: str) -> None:
        """Handle /commands."""
        output = self.query_one(OutputPane)
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        handlers = {
            "/help": self._cmd_help,
            "/status": self._cmd_status,
            "/checkpoint": self._cmd_checkpoint,
            "/events": self._cmd_events,
            "/onboard": self._cmd_onboard,
            "/model": self._cmd_model,
            "/ping": self._cmd_ping,
            "/reset": self._cmd_reset,
            "/cancel": self._cmd_cancel,
        }
        if cmd in handlers:
            await handlers[cmd]()
        elif cmd == "/skills":
            await self._cmd_skills(args)
        elif cmd == "/tools":
            await self._cmd_tools(args)
        elif cmd == "/game":
            await self._cmd_game(args)
        elif cmd == "/clear":
            output.clear()
        elif cmd == "/quit":
            self.exit()
        else:
            output.write_system(f"Unknown command: {escape(cmd)}")

    async def _cmd_help(self) -> None:
        self.query_one(OutputPane).write_system(
            "═══ Super-MCP Commands ═══\n"
            "  <text>              — Send a message to the model\n"
            "  /model              — Show the active provider and model\n"
            "  /ping               — Health-check the provider\n"
            "  /reset              — Forget the chat history\n"
            "  /cancel             — Stop the streaming response (also Esc)\n"
            "  /skills [filter]    — Browse skills\n"
            "  /tools [filter]     — Browse tools\n"
            "  /status             — Kernel status\n"
            "  /onboard            — Run onboarding\n"
            "  /game dnd|adventure|zork — Launch a game; /quit inside a game ends it\n"
            "  /checkpoint         — Save checkpoint\n"
            "  /events             — Recent events\n"
            "  /clear              — Clear output\n"
            "  /quit               — Quit\n"
            "\nKeyboard:\n"
            "  F1: Help  F2: Skills  F3: Tools  F4: Games\n"
            "  F5: Toggle Events  Ctrl+S: Toggle Sidebar\n"
            "  Ctrl+L: Clear  Ctrl+Q: Quit  Esc: Cancel stream / focus input"
        )

    async def _cmd_status(self) -> None:
        status = self.kernel.status
        self.query_one(OutputPane).write_system(
            "═══ Kernel Status ═══\n"
            f"  Booted:      {status['booted']}\n"
            f"  Session:     {status['session_id']}\n"
            f"  State:       {status['session_state']}\n"
            f"  Skills:      {status['skills_registered']}\n"
            f"  Tools:       {status['tools_registered']}\n"
            f"  Checkpoints: {status['checkpoints']}\n"
            f"  Artifacts:   {status['artifacts']}\n"
            f"  Events:      {status['events_total']}\n"
            f"  Safety:      {escape(str(status['safety_stats']))}"
        )

    async def _cmd_skills(self, filter_text: str = "") -> None:
        output = self.query_one(OutputPane)
        skills = self.kernel.skill_registry.list_all()
        if filter_text:
            needle = filter_text.lower()
            skills = [s for s in skills if needle in s.name.lower() or needle in s.slug]
        if not skills:
            output.write_system("No skills found matching filter.")
            return
        output.write_system(f"═══ Skills ({len(skills)}) ═══")
        for skill in skills[:50]:
            output.write_plain(f"  [{skill.category.value:>12}] {skill.slug:<35} {skill.name}")
        if len(skills) > 50:
            output.write_system(
                f"  ... and {len(skills) - 50} more. Use /skills <filter> to narrow."
            )

    async def _cmd_tools(self, filter_text: str = "") -> None:
        output = self.query_one(OutputPane)
        tools = self.kernel.tool_registry.list_all()
        if filter_text:
            needle = filter_text.lower()
            tools = [t for t in tools if needle in t.name.lower() or needle in t.slug]
        if not tools:
            output.write_system("No tools found matching filter.")
            return
        output.write_system(f"═══ Tools ({len(tools)}) ═══")
        for tool in tools[:50]:
            icon = {"healthy": "●", "degraded": "◐", "down": "○"}.get(tool.health.value, "?")
            output.write_plain(f"  {icon} {tool.slug:<25} {tool.name}")

    # ── Games ────────────────────────────────────────────────────

    def _set_mode(self, mode: str) -> None:
        self._ui_mode = mode
        self._refresh_status()

    async def _cmd_game(self, args: str) -> None:
        output = self.query_one(OutputPane)
        arg = args.strip().lower()
        if arg in ("quit", "exit"):
            if self._active_game:
                await self._handle_game_input("/quit")
            else:
                output.write_system("No game is running.")
            return
        if not arg:
            output.write_system(
                "Available games:\n"
                "  /game dnd       — AI D&D Quest Engine\n"
                "  /game adventure — Choose Your Own Adventure\n"
                "  /game zork      — The Ruins of Zyl (Interactive Fiction)"
            )
            return
        if arg not in self.game_runner.available_games():
            output.write_error(f"Unknown game: {arg}")
            return
        if self._active_game:
            output.write_system("A game is already running; /quit it first.")
            return

        game_id, intro = await self.game_runner.start_game(arg)
        if intro.error or not game_id:
            output.write_error(f"Failed to start game: {intro.error}")
            return
        self._active_game = arg
        self._active_game_id = game_id
        self._set_mode("GAME")
        self.query_one(InputBar).set_prompt("game▶ ")
        self._write_game_output(intro)

    async def _handle_game_input(self, user_input: str) -> None:
        """Forward input to the active game."""
        if not self._active_game_id:
            return
        result = await self.game_runner.process_turn(self._active_game_id, user_input)
        self._write_game_output(result)
        if result.game_over:
            self._active_game = None
            self._active_game_id = None
            self.query_one(InputBar).set_prompt("▶ ")
            self._set_mode("COMMAND")
            self.query_one(OutputPane).write_system("Game ended. Returned to command mode.")

    def _write_game_output(self, result: GameOutput) -> None:
        output = self.query_one(OutputPane)
        if result.narrative:
            output.write_game(result.narrative)
        if result.error and result.error != result.narrative:
            output.write_error(result.error)

    # ── Onboarding / checkpoints / events ───────────────────────

    async def _cmd_onboard(self) -> None:
        from src.onboarding.engine import OnboardingEngine

        output = self.query_one(OutputPane)
        self._set_mode("ONBOARDING")
        output.write_system("Starting onboarding...")
        try:
            report = await OnboardingEngine(self.kernel).run()
        except Exception as exc:  # noqa: BLE001 - surface any onboarding failure in the UI
            output.write_error(f"Onboarding failed: {exc}")
            self._set_mode("COMMAND")
            return
        output.write_system("═══ Onboarding Report ═══")
        for step in report.steps:
            icon, color = ("✓", "green") if step.success else ("✗", "red")
            output.write(
                f"  [{color}]{icon}[/{color}] {escape(step.step.value)} ({step.duration_ms:.0f}ms)"
            )
            for w in step.warnings:
                output.write_plain(f"    ⚠ {w}", "yellow")
        total_ms = sum(s.duration_ms for s in report.steps)
        ok = sum(1 for s in report.steps if s.success)
        output.write_system(f"\nTotal: {total_ms:.0f}ms  Success: {ok}/{len(report.steps)}")
        header = self.query_one(HeaderBar)
        header.skill_count = self.kernel.skill_registry.count
        header.tool_count = self.kernel.tool_registry.count
        header.session_state = self.kernel.session.state.value
        self._set_mode("COMMAND")

    async def _cmd_checkpoint(self) -> None:
        state = {"mode": self._ui_mode, "active_game": self._active_game}
        cp = await self.kernel.checkpoint(state)
        self.query_one(OutputPane).write_success(
            f"Checkpoint created: {cp.id}\n  Sequence: {cp.sequence}  Checksum: {cp.checksum}"
        )

    async def _cmd_events(self) -> None:
        output = self.query_one(OutputPane)
        events = self.kernel.event_bus.history(limit=20)
        output.write_system(f"═══ Recent Events ({len(events)}) ═══")
        for ev in events:
            ts = ev.timestamp.strftime("%H:%M:%S")
            output.write_plain(f"  [{ts}] {ev.severity.value:>5} [{ev.source}] {ev.kind}")

    # ── Chat ─────────────────────────────────────────────────────

    @property
    def chat_busy(self) -> bool:
        return self._chat_worker is not None and not self._chat_worker.is_finished

    def _start_chat(self, text: str) -> None:
        output = self.query_one(OutputPane)
        if self.chat is None:
            output.write_error(
                f"Chat disabled: {self._chat_unavailable or 'no provider configured'}. "
                "Relaunch with --provider/--model or create a providers.toml."
            )
            return
        if self.chat_busy:
            output.write_system("Still answering — press Esc to cancel first.")
            return
        self._chat_worker = self.run_worker(
            self._run_chat(text), name="chat", group="chat", exit_on_error=False
        )

    async def _run_chat(self, text: str) -> None:
        from src.harness.errors import HarnessError
        from src.harness.types import Finish, TextDelta, ToolCallDelta
        from src.harness.types import Usage as UsageT

        assert self.chat is not None  # noqa: S101 - guarded by _start_chat
        session = self.chat
        provider = session.provider
        output = self.query_one(OutputPane)
        bus = self.kernel.event_bus
        label = f"{provider.model or provider.name}›"
        output.begin_stream(label)
        self._set_mode("STREAMING")
        await bus.emit(
            "llm.request", "harness", {"provider": provider.name, "model": provider.model}
        )
        usage = UsageT()
        finish = "incomplete"
        outcome = "completed"
        try:
            async for event in session.stream_turn(text):
                if isinstance(event, TextDelta):
                    output.append_stream(event.text)
                elif isinstance(event, ToolCallDelta):
                    if event.name:
                        output.append_stream(f"\n⚙ tool call: {event.name}(")
                    if event.arguments:
                        output.append_stream(event.arguments)
                elif isinstance(event, UsageT):
                    usage = usage.merge(event)
                    self._refresh_status(usage)
                elif isinstance(event, Finish):
                    finish = event.reason
        except asyncio.CancelledError:
            outcome = "cancelled"
            output.end_stream("[cancelled]")
            await bus.emit("llm.cancelled", "harness", {"provider": provider.name})
            raise
        except HarnessError as err:
            outcome = "error"
            output.end_stream("[failed]")
            output.write_error(f"{type(err).__name__}: {err}")
            await bus.emit(
                "llm.error",
                "harness",
                {"provider": provider.name, "error": type(err).__name__},
                severity=Severity.ERROR,
            )
        else:
            suffix = "" if finish in ("stop", "tool_calls") else f"[finish: {finish}]"
            output.end_stream(suffix)
            await bus.emit(
                "llm.completed",
                "harness",
                {
                    "provider": provider.name,
                    "finish": finish,
                    "in": usage.input_tokens,
                    "out": usage.output_tokens,
                },
            )
        finally:
            if output.streaming:
                output.end_stream()
            self._set_mode("GAME" if self._active_game else "COMMAND")
            self._refresh_status(usage if outcome == "completed" else None)

    def _on_provider_retry(self, err: HarnessError, attempt: int, delay: float) -> None:
        if self.is_running:
            self.query_one(
                StatusBar
            ).health_text = f"{type(err).__name__}: retry {attempt} in {delay:.1f}s"

    def _refresh_status(self, last: Usage | None = None) -> None:
        if not self.is_running:
            return
        status = self.query_one(StatusBar)
        status.mode = self._ui_mode
        if self.chat is None:
            status.health_text = "chat: off"
            return
        p = self.chat.provider
        total = self.chat.total_usage
        parts = [f"{p.name}:{p.model or '?'}"]
        if last is not None and last.total_tokens:
            parts.append(f"last {last.input_tokens}→{last.output_tokens}")
        if total.total_tokens:
            parts.append(f"session {total.total_tokens} tok")
        status.health_text = " · ".join(parts)

    async def _cmd_model(self) -> None:
        self._describe_chat(self.query_one(OutputPane))

    async def _cmd_ping(self) -> None:
        output = self.query_one(OutputPane)
        if self.chat is None:
            self._describe_chat(output)
            return
        report = await self.chat.provider.check_health()
        line = (
            f"{report.provider} @ {report.endpoint}: "
            f"{'reachable' if report.ok else 'FAILED'} ({report.latency_ms:.0f} ms) — "
            f"{report.detail}"
        )
        if report.ok:
            output.write_plain(line, "bold green")
        else:
            output.write_error(line)

    async def _cmd_reset(self) -> None:
        if self.chat is not None:
            if self.chat_busy:
                await self._cmd_cancel()
            self.chat.reset()
            self.query_one(OutputPane).write_system("Chat history cleared.")

    async def _cmd_cancel(self) -> None:
        if self.chat_busy and self._chat_worker is not None:
            self._chat_worker.cancel()
            await self.workers.wait_for_complete([self._chat_worker])
        else:
            self.query_one(OutputPane).write_system("Nothing is streaming.")

    # ── Actions ──────────────────────────────────────────────────

    async def action_cancel_or_focus(self) -> None:
        if self.chat_busy and self._chat_worker is not None:
            self._chat_worker.cancel()
        else:
            self.query_one(InputBar).focus_input()

    async def action_show_help(self) -> None:
        await self._cmd_help()

    def action_focus_tab(self, tab_id: str) -> None:
        self.query_one("#sidebar-tabs", TabbedContent).active = tab_id

    def action_toggle_events(self) -> None:
        event_log = self.query_one(EventLog)
        self._events_visible = not self._events_visible
        event_log.display = self._events_visible

    def action_toggle_sidebar(self) -> None:
        sidebar = self.query_one("#sidebar-toggle")
        self._sidebar_visible = not self._sidebar_visible
        sidebar.display = self._sidebar_visible

    def action_clear_output(self) -> None:
        self.query_one(OutputPane).clear()

    def action_focus_input(self) -> None:
        self.query_one(InputBar).focus_input()


_GAME_META = {"/help", "/save", "/load", "/undo", "/redo", "/status", "/quit", "/replay"}


def _is_game_meta(command: str) -> bool:
    return command.split(maxsplit=1)[0].lower() in _GAME_META


def run_tui(
    *,
    chat: ChatSession | None = None,
    chat_unavailable: str | None = None,
    initial_prompt: str | None = None,
) -> None:
    """Entry point for the TUI."""
    SuperMCPApp(chat=chat, chat_unavailable=chat_unavailable, initial_prompt=initial_prompt).run()
