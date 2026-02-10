"""Super-MCP CLI — primary entry point.

Provides the `super-mcp` and `smcp` commands with subcommands
for launching the TUI, running onboarding, playing games,
managing skills/tools, and exporting artifacts.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
)

logger = structlog.get_logger(__name__)


@click.group(invoke_without_command=True)
@click.version_option(version="1.0.0", prog_name="super-mcp")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Super-MCP — Universal Model Context Protocol Platform.

    Launch the TUI with no subcommand, or use subcommands for
    specific operations.
    """
    if ctx.invoked_subcommand is None:
        # Default: launch TUI
        ctx.invoke(tui)


@cli.command()
def tui() -> None:
    """Launch the Terminal User Interface."""
    click.echo("⚡ Starting Super-MCP TUI...")
    from src.tui.app import run_tui
    run_tui()


@cli.command()
def onboard() -> None:
    """Run the onboarding wizard."""
    click.echo("⚡ Running Super-MCP Onboarding...\n")

    async def _run() -> None:
        from src.kernel.kernel import Kernel
        from src.onboarding.engine import OnboardingEngine

        kernel = Kernel()
        await kernel.boot()

        engine = OnboardingEngine(kernel)
        report = await engine.run()

        click.echo("\n═══ Onboarding Report ═══")
        for step in report.steps:
            icon = click.style("✓", fg="green") if step.success else click.style("✗", fg="red")
            click.echo(f"  {icon} {step.step_name} ({step.duration_ms:.0f}ms)")
            if step.warnings:
                for w in step.warnings:
                    click.echo(click.style(f"    ⚠ {w}", fg="yellow"))

        total = sum(1 for s in report.steps if s.success)
        click.echo(f"\nTotal: {report.total_duration_ms:.0f}ms  Success: {total}/{len(report.steps)}")

        await kernel.shutdown()

    asyncio.run(_run())


@cli.command()
@click.argument("game_type", type=click.Choice(["dnd", "adventure", "zork"]))
def play(game_type: str) -> None:
    """Launch a game in terminal mode.

    GAME_TYPE: dnd, adventure, or zork
    """
    async def _run() -> None:
        from src.games.dnd.game import DnDGame
        from src.games.adventure.game import AdventureGame
        from src.games.zork.game import ZorkGame

        games = {
            "dnd": DnDGame,
            "adventure": AdventureGame,
            "zork": ZorkGame,
        }

        game = games[game_type]()
        intro = await game.initialize()
        click.echo(intro)

        while True:
            try:
                user_input = click.prompt("", prompt_suffix="> ", type=str)
            except (EOFError, KeyboardInterrupt):
                click.echo("\nGoodbye!")
                break

            if user_input.strip().lower() in ("quit", "exit", "/quit"):
                summary = await game.generate_summary()
                click.echo(f"\n{summary}")
                click.echo("Goodbye!")
                break

            response = await game.process_input(user_input)
            click.echo(response)

    asyncio.run(_run())


@cli.command()
@click.option("--filter", "-f", default="", help="Filter skills by name/category")
def skills(filter: str) -> None:
    """List all registered skills."""
    async def _run() -> None:
        from src.kernel.kernel import Kernel
        from src.skills.catalog.generator import SKILL_DEFINITIONS

        click.echo(f"═══ Super-MCP Skill Catalog ({len(SKILL_DEFINITIONS)} skills) ═══\n")

        for skill in SKILL_DEFINITIONS:
            if filter and filter.lower() not in skill["name"].lower() and filter.lower() not in skill.get("category", ""):
                continue
            cat = skill.get("category", "system")
            click.echo(f"  [{cat:>12}] {skill['slug']:<35} {skill['name']}")

    asyncio.run(_run())


@cli.command()
@click.option("--filter", "-f", default="", help="Filter tools by name")
def tools(filter: str) -> None:
    """List all registered tools."""
    async def _run() -> None:
        from src.tools.registry.catalog import TOOL_CATALOG

        click.echo(f"═══ Super-MCP Tool Registry ({len(TOOL_CATALOG)} tools) ═══\n")

        for tool in TOOL_CATALOG:
            if filter and filter.lower() not in tool.name.lower():
                continue
            auth = tool.auth_type.value if hasattr(tool.auth_type, "value") else str(tool.auth_type)
            click.echo(f"  [{auth:>10}] {tool.slug:<25} {tool.name}")

    asyncio.run(_run())


@cli.command()
def status() -> None:
    """Show kernel status."""
    async def _run() -> None:
        from src.kernel.kernel import Kernel

        kernel = Kernel()
        await kernel.boot()

        s = kernel.status
        click.echo("═══ Super-MCP Kernel Status ═══\n")
        for key, val in s.items():
            click.echo(f"  {key:<20} {val}")

        await kernel.shutdown()

    asyncio.run(_run())


@cli.command()
@click.argument("output_dir", type=click.Path(), default=".")
def generate_skills(output_dir: str) -> None:
    """Generate skill .md files to a directory."""
    async def _run() -> None:
        from src.skills.catalog.generator import generate_catalog

        path = Path(output_dir)
        count = await generate_catalog(path)
        click.echo(f"Generated {count} skill files to {path}")

    asyncio.run(_run())


@cli.command()
def export_report() -> None:
    """Export a session report."""
    async def _run() -> None:
        from src.kernel.kernel import Kernel
        from src.artifacts.exporter import ArtifactExporter

        kernel = Kernel()
        await kernel.boot()

        exporter = ArtifactExporter()
        path = await exporter.export_session_report(kernel.status)
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
