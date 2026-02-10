# Super-MCP

**Universal MCP platform — canonical skills, verified tools, games, and one-command onboarding for any AI agent.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

---

## What Is This?

Super-MCP is a production-grade Model Context Protocol platform that ships with **120 skills**, **54 verified tools**, **3 interactive games**, a keyboard-first **TUI**, and a complete observability stack. It is agent-agnostic, fully auditable, deterministically replayable, and designed for extension.

### Highlights

| Layer | What You Get |
|---|---|
| **Kernel** | Async event bus, generic registries, declarative safety rules, session lifecycle |
| **Skills** | 120 Skill.md artifacts across code, data, security, DevOps, writing, research, games |
| **Tools** | 54 tool definitions with OAuth2+PKCE, health checks, categorized registry |
| **Games** | D&D Quest Engine, Choose-Your-Own-Adventure (3 stories), Zork-style Interactive Fiction |
| **TUI** | Textual-based terminal UI with sidebar, event log, output pane, game launcher |
| **Onboarding** | 7-step wizard: environment check, OAuth, skill loading, tool verification, health |
| **Replay** | Deterministic event capture, annotated bundles, speed-controlled playback |
| **Analytics** | Usage tracking, aggregated reports, trend analysis, JSON export |
| **Observability** | Counters, gauges, histograms, OpenTelemetry-compatible spans, Prometheus export |
| **Security** | Sandboxed execution with memory/CPU/timeout limits, command/path validation |
| **Hooks** | 25+ extension points with prioritized before/after plugin callbacks |

---

## Quick Start

### Install

```bash
# Clone and install
git clone https://github.com/super-mcp/super-mcp.git
cd super-mcp
pip install -e ".[all]"
```

### Launch the TUI

```bash
smcp tui
# or simply:
smcp
```

### Run Onboarding

```bash
smcp onboard
```

### Play a Game

```bash
smcp play dnd        # D&D Quest Engine
smcp play adventure  # Choose-Your-Own-Adventure
smcp play zork       # The Ruins of Zyl
```

---

## CLI Reference

All commands are available via `super-mcp` or the `smcp` alias.

```
smcp [COMMAND]

Commands:
  tui               Launch the terminal UI (default)
  onboard           Run the onboarding wizard
  play TYPE         Start a game (dnd | adventure | zork)
  skills            List registered skills
  tools             List registered tools
  status            Show kernel status and health
  generate-skills   Generate Skill.md files to disk
  export-report     Export a session analytics report
  metrics           Display observability metrics

Options:
  --help            Show help for any command
```

### Examples

```bash
smcp skills --filter "security"    # Filter skills by tag
smcp tools --filter "github"       # Filter tools by name
smcp generate-skills --output-dir ./my-skills
smcp export-report --output report.json
```

---

## TUI

The TUI is the primary interface. It combines a sidebar browser, output pane, event log, and game integration into a single keyboard-driven experience.

### Keyboard Shortcuts

| Key | Action |
|---|---|
| `F1` | Help |
| `F2` | Focus Skills panel |
| `F3` | Focus Tools panel |
| `F4` | Focus Games panel |
| `F5` | Toggle Event Log |
| `Ctrl+S` | Toggle Sidebar |
| `Ctrl+L` | Clear output |
| `Ctrl+Q` | Quit |
| `Esc` | Focus input bar |

### Slash Commands

| Command | Description |
|---|---|
| `/help` | Show available commands |
| `/skills` | List all loaded skills |
| `/tools` | List all registered tools |
| `/status` | Kernel status and health |
| `/onboard` | Start onboarding wizard |
| `/game <type>` | Launch a game (`dnd`, `adventure`, `zork`) |
| `/checkpoint` | Create a named checkpoint |
| `/events` | Show recent events |
| `/clear` | Clear output pane |
| `/quit` | Exit the TUI |

When a game is active, any non-slash input is forwarded to the game engine. Type `/quit` to exit the game and return to command mode.

---

## Games

### D&D Quest Engine

A complete tabletop RPG experience. Create a character (Warrior, Mage, Rogue, Ranger, Cleric), explore procedurally structured encounters, engage in turn-based combat with initiative rolls, and level up as you progress. Features character sheets, dice mechanics (d4–d20), rest/heal systems, and boss encounters.

### Choose-Your-Own-Adventure

Three fully branching narrative stories:
- **The Crystal Caverns** — Explore underground caves with survival choices
- **Starship Artemis** — Sci-fi command bridge decisions aboard a damaged vessel
- **The Enchanted Library** — Magical library with puzzle rooms and hidden paths

Each story has ~20 nodes with multiple endings. Choices are tracked and scored.

### The Ruins of Zyl (Zork-style)

A parser-based interactive fiction game with 14 rooms, 14 items, 5 NPCs, and a natural-language command parser supporting 20+ verbs. Features include dark rooms (bring a lantern or face the grue), NPC puzzles (riddles, bribery, combat), inventory management with weight limits, equipped weapons and armor, and a score/rank system. Your goal: restore the Crystal of Zyl to the Deep Vault.

All games support **undo/redo**, **named checkpoints**, and **deterministic replay** via the game engine state manager.

---

## Architecture

Super-MCP is built on five layers:

```
┌─────────────────────────────────────────┐
│  TUI / CLI                              │  ← User-facing
├─────────────────────────────────────────┤
│  Games / Onboarding                     │  ← Interactive modules
├─────────────────────────────────────────┤
│  Skills / Tools / Hooks                 │  ← Capability layer
├─────────────────────────────────────────┤
│  Replay / Analytics / Observability     │  ← Cross-cutting concerns
├─────────────────────────────────────────┤
│  Kernel (Event Bus, Registries, Safety) │  ← Foundation
└─────────────────────────────────────────┘
```

The **Kernel** owns the lifecycle (`boot → onboard → run → checkpoint → shutdown`), emits all state changes through an async event bus, and enforces safety rules before any tool execution.

For a detailed architectural walkthrough, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Extension Points

Super-MCP exposes **25+ hook points** for plugins:

- **Lifecycle**: `kernel.boot`, `kernel.shutdown`, `session.start`, `session.end`
- **Skills**: `skill.register`, `skill.invoke`, `skill.complete`
- **Tools**: `tool.register`, `tool.invoke`, `tool.health_check`
- **Events**: `event.emit`, `event.subscribe`
- **Safety**: `safety.check`, `safety.violation`
- **Games**: `game.start`, `game.input`, `game.end`
- **Onboarding**: `onboard.start`, `onboard.step`, `onboard.complete`

Hooks are async, prioritized (lower number = earlier execution), and support both `before` and `after` semantics.

For the full plugin development guide, see [EXTENDING.md](EXTENDING.md).

---

## Development

### Setup

```bash
git clone https://github.com/super-mcp/super-mcp.git
cd super-mcp
pip install -e ".[dev]"
```

### Test

```bash
pytest                        # Run all tests
pytest --cov=src              # With coverage
pytest -m "not slow"          # Skip slow tests
pytest tests/unit/            # Unit tests only
```

### Lint & Type Check

```bash
ruff check src/               # Lint
ruff format src/               # Format
mypy src/                      # Type check
```

### Generate Skills

```bash
smcp generate-skills --output-dir ./skills
```

---

## Project Structure

```
src/
├── cli.py                     # Click CLI entry point
├── kernel/                    # Core: types, event bus, registries, safety, kernel
├── skills/                    # Skill loader and 120-skill catalog generator
├── tools/                     # Tool registry (54 tools) and OAuth2+PKCE manager
├── onboarding/                # 7-step onboarding wizard
├── games/                     # Game engine + 3 games (D&D, Adventure, Zork)
├── tui/                       # Textual TUI app, themes, 6 components
├── replay/                    # Deterministic replay engine
├── analytics/                 # Usage tracking and reporting
├── observability/             # Metrics, counters, histograms, tracing
├── artifacts/                 # Session and artifact export
├── security/                  # Sandboxed execution
└── api/                       # Plugin hook registry

skills/                        # 120 Skill.md artifact files
tests/                         # Unit, integration, and e2e tests
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
