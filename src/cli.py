"""Super-MCP CLI — primary entry point.

Provides the `super-mcp` and `smcp` commands with subcommands for launching
the TUI, chatting with a model provider, running onboarding, playing games,
managing skills/tools, and exporting artifacts.

Provider selection (``--provider/--model/--endpoint/--config/--api-key-env/
--api-key-file``) is a group option, so it applies to ``tui``, ``start``,
``ping`` and ``providers`` alike::

    smcp -p ollama -m qwen2.5:0.5b ping
    smcp -p anthropic -m claude-sonnet-4-5 start
    echo "summarise this" | smcp -p lmstudio -m hermes-3 start
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, TextIO

import click
import structlog

from src.harness.config import (
    HarnessConfig,
    ProviderProfile,
    all_profiles,
    key_status,
    resolve_profile,
)
from src.harness.errors import HarnessError

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.games.engine.runner import GameInterface
    from src.harness.session import ChatSession


class _StderrLoggerFactory:
    """structlog output goes to the *current* ``sys.stderr``.

    Keeps stdout clean for piped model output, and lets the TUI's stderr
    capture take over while it runs.
    """

    def __call__(self, *args: Any) -> structlog.PrintLogger:  # noqa: ARG002
        return structlog.PrintLogger(file=sys.stderr)


structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
    logger_factory=_StderrLoggerFactory(),
)

logger = structlog.get_logger(__name__)

EXIT_CANCELLED = 130


@dataclass(frozen=True, slots=True)
class HarnessOptions:
    provider: str | None
    model: str | None
    endpoint: str | None
    config: Path | None
    api_key_env: str | None
    api_key_file: Path | None

    def load_config(self) -> HarnessConfig:
        return HarnessConfig.load(self.config)

    def profile(self, config: HarnessConfig | None = None) -> ProviderProfile:
        return resolve_profile(
            config or self.load_config(),
            self.provider,
            model=self.model,
            endpoint=self.endpoint,
            api_key_env=self.api_key_env,
            api_key_file=self.api_key_file,
        )


def _fail(err: HarnessError) -> NoReturn:
    click.secho(f"error: {type(err).__name__}: {err}", err=True, fg="red")
    sys.exit(err.exit_code)


def _options(ctx: click.Context) -> HarnessOptions:
    opts = ctx.find_object(HarnessOptions)
    if opts is None:  # pragma: no cover - the group always sets it
        raise click.UsageError("provider options not initialised")
    return opts


def _build_session(
    opts: HarnessOptions,
    *,
    system: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> ChatSession:
    from src.harness.registry import build_provider
    from src.harness.session import ChatSession

    profile = opts.profile()
    provider = build_provider(profile)
    return ChatSession(
        provider, system_prompt=system, temperature=temperature, max_tokens=max_tokens
    )


@click.group(invoke_without_command=True)
@click.version_option(version="1.0.0", prog_name="super-mcp")
@click.option(
    "--provider",
    "-p",
    envvar="SMCP_PROVIDER",
    help="Profile or preset: ollama, lmstudio, vllm, openai, anthropic, openai-compatible, "
    "or a name from providers.toml.",
)
@click.option("--model", "-m", envvar="SMCP_MODEL", help="Model identifier.")
@click.option("--endpoint", "-e", help="Override the base URL (e.g. http://host:8000/v1).")
@click.option(
    "--config",
    "-c",
    "config_path",
    type=click.Path(path_type=Path, dir_okay=False),
    help="providers.toml (default: $SMCP_PROVIDERS_FILE or ~/.config/super-mcp/providers.toml).",
)
@click.option(
    "--api-key-env",
    metavar="VAR",
    help="Read the API key from this environment variable (or VAR_FILE).",
)
@click.option(
    "--api-key-file",
    type=click.Path(path_type=Path, dir_okay=False),
    help="Read the API key from this file (one line).",
)
@click.pass_context
def cli(
    ctx: click.Context,
    provider: str | None,
    model: str | None,
    endpoint: str | None,
    config_path: Path | None,
    api_key_env: str | None,
    api_key_file: Path | None,
) -> None:
    """Super-MCP — Universal Model Context Protocol Platform.

    Launch the TUI with no subcommand, or use subcommands for
    specific operations.
    """
    ctx.obj = HarnessOptions(
        provider=provider,
        model=model,
        endpoint=endpoint,
        config=config_path,
        api_key_env=api_key_env,
        api_key_file=api_key_file,
    )
    if ctx.invoked_subcommand is None:
        ctx.invoke(tui)


@cli.command()
@click.pass_context
def tui(ctx: click.Context) -> None:
    """Launch the Terminal User Interface (chat disabled if no provider resolves)."""
    from src.tui.app import run_tui

    chat: ChatSession | None = None
    reason: str | None = None
    try:
        chat = _build_session(_options(ctx))
    except HarnessError as err:
        reason = str(err)
    run_tui(chat=chat, chat_unavailable=reason)


# ── Provider commands ───────────────────────────────────────────


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@click.pass_context
def ping(ctx: click.Context, as_json: bool) -> None:
    """Health-check the selected provider endpoint (and model, if given)."""
    from src.harness.registry import build_provider

    try:
        profile = _options(ctx).profile()
        provider = build_provider(profile)
    except HarnessError as err:
        _fail(err)

    async def _run() -> Any:
        async with provider:
            return await provider.check_health()

    report = asyncio.run(_run())
    if as_json:
        click.echo(
            json.dumps(
                {
                    "ok": report.ok,
                    "provider": report.provider,
                    "endpoint": report.endpoint,
                    "model": report.model or None,
                    "model_available": report.model_available,
                    "latency_ms": round(report.latency_ms, 1),
                    "detail": report.detail,
                    "error": type(report.error).__name__ if report.error else None,
                    "models": list(report.models),
                }
            )
        )
    else:
        target = f"{report.provider} @ {report.endpoint}"
        if report.ok:
            click.secho(f"✓ {target} reachable ({report.latency_ms:.0f} ms)", fg="green")
        else:
            click.secho(f"✗ {target} FAILED", fg="red", err=True)
        click.echo(f"  {report.detail}", err=not report.ok)
        if report.model and report.model_available:
            click.echo(f"  model {report.model!r} available")
    if not report.ok:
        sys.exit(report.error.exit_code if report.error else 1)


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@click.pass_context
def providers(ctx: click.Context, as_json: bool) -> None:
    """List presets and configured profiles. Keys are never printed."""
    opts = _options(ctx)
    try:
        config = opts.load_config()
        active = opts.profile(config).name
    except HarnessError as err:
        _fail(err)
    rows = []
    for name, profile in all_profiles(config).items():
        rows.append(
            {
                "active": name == active,
                "name": name,
                "kind": profile.kind,
                "base_url": profile.base_url or "(set --endpoint)",
                "model": profile.model or "",
                "key": key_status(profile),
                "source": "config" if name in config.profiles else "preset",
            }
        )
    if as_json:
        click.echo(
            json.dumps({"config": str(config.source) if config.source else None, "providers": rows})
        )
        return
    click.echo(f"Config: {config.source or '(none — presets only)'}\n")
    for r in rows:
        mark = "*" if r["active"] else " "
        click.echo(
            f" {mark} {r['name']:<18} {r['kind']:<9} {r['base_url']:<34} "
            f"{(r['model'] or '-'):<22} key: {r['key']}"
        )


@cli.command()
@click.argument("prompt", required=False)
@click.option(
    "--tui/--no-tui",
    "use_tui",
    default=None,
    help="Force the TUI or plain streaming. Default: TUI on an interactive terminal "
    "with no PROMPT, plain otherwise.",
)
@click.option("--system", "system_prompt", help="System prompt text.")
@click.option(
    "--system-file",
    type=click.Path(path_type=Path, dir_okay=False, exists=True),
    help="Read the system prompt from a file.",
)
@click.option("--temperature", "-t", type=click.FloatRange(0.0, 2.0), default=None)
@click.option("--max-tokens", type=click.IntRange(1), default=None)
@click.option("--show-usage", is_flag=True, help="Print token usage to stderr (plain mode).")
@click.pass_context
def start(
    ctx: click.Context,
    prompt: str | None,
    use_tui: bool | None,
    system_prompt: str | None,
    system_file: Path | None,
    temperature: float | None,
    max_tokens: int | None,
    show_usage: bool,
) -> None:
    """Chat with the selected provider: TUI interactively, plain stream when piped.

    In plain mode the prompt is PROMPT, piped stdin, or both (PROMPT first).
    The answer streams to stdout; diagnostics go to stderr. Ctrl+C cancels.
    """
    if system_file is not None:
        system_prompt = system_file.read_text(encoding="utf-8")
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    tui_mode = use_tui if use_tui is not None else (interactive and prompt is None)

    try:
        session = _build_session(
            _options(ctx), system=system_prompt, temperature=temperature, max_tokens=max_tokens
        )
        if not session.provider.model:
            from src.harness.errors import ConfigError

            raise ConfigError(
                "no model selected; pass --model or set model in the profile",
                provider=session.provider.name,
            )
    except HarnessError as err:
        _fail(err)

    if tui_mode:
        if not sys.stdout.isatty():
            raise click.UsageError("--tui needs an interactive terminal; use --no-tui")
        from src.tui.app import run_tui

        run_tui(chat=session, initial_prompt=prompt)
        return

    text = _collect_prompt(prompt, sys.stdin)
    if not text.strip():
        raise click.UsageError("empty prompt: pass PROMPT or pipe text on stdin")
    try:
        code = asyncio.run(_stream_plain(session, text, sys.stdout, show_usage=show_usage))
    except KeyboardInterrupt:
        click.echo("\n[cancelled]", err=True)
        code = EXIT_CANCELLED
    sys.exit(code)


def _stdin_has_input(stdin: TextIO) -> bool:
    """True when stdin is a pipe or a redirected file.

    A terminal, ``/dev/null`` or an inherited socket (CI runners, agent
    shells) is not treated as input, so ``smcp start "prompt"`` never blocks
    waiting on a stream that will not close.
    """
    try:
        mode = os.fstat(stdin.fileno()).st_mode
    except (OSError, ValueError, io.UnsupportedOperation):
        return False
    return stat.S_ISFIFO(mode) or stat.S_ISREG(mode)


def _collect_prompt(prompt: str | None, stdin: TextIO) -> str:
    piped = stdin.read() if _stdin_has_input(stdin) else ""
    if prompt and piped:
        return f"{prompt}\n\n{piped}"
    if prompt:
        return prompt
    if piped:
        return piped
    if stdin.isatty():
        return str(click.prompt("Prompt"))
    return ""


async def _stream_plain(
    session: ChatSession, text: str, out: TextIO, *, show_usage: bool = False
) -> int:
    """Stream one turn to ``out``. Returns the process exit code."""
    from src.harness.types import Finish, TextDelta, Usage

    usage = Usage()
    finish = "incomplete"
    last = "\n"
    try:
        async with session.provider:
            async for event in session.stream_turn(text):
                if isinstance(event, TextDelta):
                    out.write(event.text)
                    out.flush()
                    last = event.text[-1:] or last
                elif isinstance(event, Usage):
                    usage = usage.merge(event)
                elif isinstance(event, Finish):
                    finish = event.reason
    except HarnessError as err:
        if last != "\n":
            out.write("\n")
        click.secho(f"error: {type(err).__name__}: {err}", err=True, fg="red")
        return err.exit_code
    except BrokenPipeError:
        return 0
    if last != "\n":
        out.write("\n")
        out.flush()
    result = session.last_result
    for call in result.tool_calls if result else ():
        click.echo(f"[tool call] {call.name}({call.arguments}) id={call.id}", err=True)
    if finish not in ("stop", "tool_calls"):
        click.secho(f"[finish: {finish}]", err=True, fg="yellow")
    if show_usage:
        click.echo(
            f"[usage] in={usage.input_tokens} out={usage.output_tokens} total={usage.total_tokens}",
            err=True,
        )
    return 0


# ── Platform commands ───────────────────────────────────────────


@cli.command()
def onboard() -> None:
    """Run the onboarding wizard."""
    click.echo("⚡ Running Super-MCP Onboarding...\n")

    async def _run() -> None:
        from src.kernel.kernel import Kernel
        from src.onboarding.engine import OnboardingEngine

        kernel = Kernel()
        await kernel.boot()
        report = await OnboardingEngine(kernel).run()

        click.echo("\n═══ Onboarding Report ═══")
        for step in report.steps:
            icon = click.style("✓", fg="green") if step.success else click.style("✗", fg="red")
            click.echo(f"  {icon} {step.step.value} ({step.duration_ms:.0f}ms)")
            for w in step.warnings:
                click.echo(click.style(f"    ⚠ {w}", fg="yellow"))

        total = sum(1 for s in report.steps if s.success)
        total_ms = sum(s.duration_ms for s in report.steps)
        click.echo(f"\nTotal: {total_ms:.0f}ms  Success: {total}/{len(report.steps)}")
        await kernel.shutdown()

    asyncio.run(_run())


@cli.command()
@click.argument("game_type", type=click.Choice(["dnd", "adventure", "zork"]))
def play(game_type: str) -> None:
    """Launch a game in terminal mode.

    GAME_TYPE: dnd, adventure, or zork
    """

    async def _run() -> None:
        from src.games.adventure.game import AdventureGame
        from src.games.dnd.game import DnDGame
        from src.games.engine.runner import GameRunner
        from src.games.zork.game import ZorkGame
        from src.kernel.event_bus import EventBus

        factories: dict[str, Callable[[], GameInterface]] = {
            "dnd": DnDGame,
            "adventure": AdventureGame,
            "zork": ZorkGame,
        }
        runner = GameRunner(EventBus())
        try:
            runner.register_game(factories[game_type]())
        except Exception as exc:  # noqa: BLE001 - report a broken game cleanly
            raise click.ClickException(f"game {game_type!r} is unavailable: {exc}") from exc
        game_id, intro = await runner.start_game(game_type)
        if intro.error:
            raise click.ClickException(intro.error)
        click.echo(intro.narrative)

        while True:
            try:
                user_input = click.prompt("", prompt_suffix="> ", type=str)
            except (EOFError, KeyboardInterrupt, click.Abort):
                click.echo("\nGoodbye!")
                break
            command = user_input.strip().lower()
            result = await runner.process_turn(
                game_id, "/quit" if command in ("quit", "exit") else user_input
            )
            click.echo(result.narrative)
            if result.game_over:
                break

    asyncio.run(_run())


@cli.command()
@click.option("--filter", "-f", "filter_text", default="", help="Filter skills by name/category")
def skills(filter_text: str) -> None:
    """List all registered skills."""
    from src.skills.catalog.generator import SKILL_DEFINITIONS

    click.echo(f"═══ Super-MCP Skill Catalog ({len(SKILL_DEFINITIONS)} skills) ═══\n")
    needle = filter_text.lower()
    for skill in SKILL_DEFINITIONS:
        cat = str(skill.get("category", "system"))
        if needle and needle not in str(skill["name"]).lower() and needle not in cat:
            continue
        click.echo(f"  [{cat:>12}] {skill['slug']:<35} {skill['name']}")


@cli.command()
@click.option("--filter", "-f", "filter_text", default="", help="Filter tools by name")
def tools(filter_text: str) -> None:
    """List all registered tools."""
    from src.tools.registry.catalog import TOOL_CATALOG

    click.echo(f"═══ Super-MCP Tool Registry ({len(TOOL_CATALOG)} tools) ═══\n")
    for tool in TOOL_CATALOG:
        if filter_text and filter_text.lower() not in tool.name.lower():
            continue
        click.echo(f"  [{tool.auth_type.value:>10}] {tool.slug:<25} {tool.name}")


@cli.command()
def status() -> None:
    """Show kernel status."""

    async def _run() -> None:
        from src.kernel.kernel import Kernel

        kernel = Kernel()
        await kernel.boot()
        click.echo("═══ Super-MCP Kernel Status ═══\n")
        for key, val in kernel.status.items():
            click.echo(f"  {key:<20} {val}")
        await kernel.shutdown()

    asyncio.run(_run())


@cli.command()
@click.argument("output_dir", type=click.Path(), default=".")
def generate_skills(output_dir: str) -> None:
    """Generate skill .md files to a directory."""
    from src.skills.catalog.generator import generate_catalog

    path = Path(output_dir)
    count = generate_catalog(path)
    click.echo(f"Generated {count} skill files to {path}")


@cli.command()
def export_report() -> None:
    """Export a session report."""

    async def _run() -> None:
        from src.artifacts.exporter import ArtifactExporter
        from src.kernel.kernel import Kernel

        kernel = Kernel()
        await kernel.boot()
        path = await ArtifactExporter().export_session_report(kernel.status)
        click.echo(f"Report exported to: {path}")
        await kernel.shutdown()

    asyncio.run(_run())


@cli.command()
def metrics() -> None:
    """Show system metrics."""
    from src.observability.metrics import MetricsRegistry

    registry = MetricsRegistry()
    click.echo("═══ Super-MCP Metrics ═══\n")
    click.echo(registry.format_prometheus() or "(No metrics collected yet)")


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
