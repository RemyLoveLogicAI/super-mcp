"""Sidebar component — skill/tool browser and navigation."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Label, ListItem, ListView, Static, TabbedContent, TabPane


class SkillBrowser(Static):
    """Browse registered skills by category."""

    class SkillSelected(Message):
        def __init__(self, skill_slug: str) -> None:
            self.skill_slug = skill_slug
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Label("Skills", classes="panel-title")
        yield ListView(id="skill-list")

    def update_skills(self, skills: list[dict]) -> None:
        """Populate skill list from registry data."""
        list_view = self.query_one("#skill-list", ListView)
        list_view.clear()
        for skill in skills:
            item = ListItem(
                Label(f"  {skill.get('name', 'Unknown')}"),
                classes="skill-item",
            )
            item.data = skill  # type: ignore[attr-defined]
            list_view.append(item)

    DEFAULT_CSS = """
    SkillBrowser {
        height: 1fr;
        padding: 0 1;
    }
    """


class ToolBrowser(Static):
    """Browse registered tools with health status."""

    class ToolSelected(Message):
        def __init__(self, tool_slug: str) -> None:
            self.tool_slug = tool_slug
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Label("Tools", classes="panel-title")
        yield ListView(id="tool-list")

    def update_tools(self, tools: list[dict]) -> None:
        """Populate tool list from registry data."""
        list_view = self.query_one("#tool-list", ListView)
        list_view.clear()
        for tool in tools:
            health = tool.get("health", "unknown")
            icon = {"healthy": "●", "degraded": "◐", "down": "○"}.get(health, "?")
            color_class = health if health in ("healthy", "degraded", "down") else ""
            item = ListItem(
                Label(f"  {icon} {tool.get('name', 'Unknown')}"),
                classes=f"tool-item {color_class}",
            )
            item.data = tool  # type: ignore[attr-defined]
            list_view.append(item)

    DEFAULT_CSS = """
    ToolBrowser {
        height: 1fr;
        padding: 0 1;
    }
    """


class GameLauncher(Static):
    """Game selection panel."""

    class GameSelected(Message):
        def __init__(self, game_type: str) -> None:
            self.game_type = game_type
            super().__init__()

    GAMES = [
        {"id": "dnd", "name": "D&D Quest Engine", "icon": "⚔️", "desc": "AI Dungeon Master"},
        {"id": "adventure", "name": "Choose Adventure", "icon": "📖", "desc": "Branching narratives"},
        {"id": "zork", "name": "Ruins of Zyl", "icon": "🏰", "desc": "Interactive fiction"},
    ]

    def compose(self) -> ComposeResult:
        yield Label("Games", classes="panel-title")
        yield ListView(id="game-list")

    def on_mount(self) -> None:
        list_view = self.query_one("#game-list", ListView)
        for game in self.GAMES:
            list_view.append(
                ListItem(Label(f"  {game['icon']} {game['name']}"), classes="skill-item")
            )

    DEFAULT_CSS = """
    GameLauncher {
        height: 1fr;
        padding: 0 1;
    }
    """


class Sidebar(Static):
    """Main sidebar with tabbed navigation."""

    def compose(self) -> ComposeResult:
        with TabbedContent(id="sidebar-tabs"):
            with TabPane("Skills", id="tab-skills"):
                yield SkillBrowser()
            with TabPane("Tools", id="tab-tools"):
                yield ToolBrowser()
            with TabPane("Games", id="tab-games"):
                yield GameLauncher()

    DEFAULT_CSS = """
    Sidebar {
        width: 35;
        background: #0f172a;
        border-right: solid #334155;
    }

    #sidebar-tabs {
        height: 1fr;
    }
    """
