# Architecture

This document describes the internal architecture of Super-MCP. It is intended for contributors and developers building extensions.

---

## Design Principles

1. **Agent-agnostic**: No assumption about which LLM or orchestration layer sits above. The kernel exposes a neutral protocol.
2. **Event-sourced**: Every state change flows through the event bus. This enables replay, audit, and analytics without coupling modules.
3. **Registry-driven**: Skills, tools, and games are all registered through the same generic `Registry[T]` pattern. Registration is the only way to make a capability visible to the system.
4. **Safety-first**: All tool invocations pass through a declarative safety layer before execution. Rules are evaluated in priority order; the first matching rule wins.
5. **Extension via hooks**: The system never requires forking. 25+ hook points allow plugins to intercept and augment behavior at every stage.

---

## Layer Diagram

```
┌──────────────────────────────────────────────────────┐
│                    User Interface                     │
│   TUI (Textual)  │  CLI (Click)  │  Future: Web API  │
├──────────────────────────────────────────────────────┤
│                  Interactive Modules                  │
│   Onboarding  │  Games (D&D, Adventure, Zork)        │
├──────────────────────────────────────────────────────┤
│                  Capability Layer                     │
│   SkillRegistry  │  ToolRegistry  │  HookRegistry    │
├──────────────────────────────────────────────────────┤
│                Cross-Cutting Concerns                 │
│   Replay  │  Analytics  │  Observability  │  Sandbox  │
├──────────────────────────────────────────────────────┤
│                      Kernel                           │
│   EventBus  │  Registry[T]  │  SafetyLayer  │  Types │
└──────────────────────────────────────────────────────┘
```

Each layer depends only on the layer below it. The kernel has zero upward dependencies.

---

## Kernel (`src/kernel/`)

### Types (`types.py`)

The type system is the foundation. All data structures are Pydantic v2 models with strict validation.

**Core types:**

| Type | Purpose |
|---|---|
| `EntityID` | UUID wrapper for all identifiable objects |
| `SkillDefinition` | Skill metadata: name, description, version, tags, parameters, examples |
| `ToolDefinition` | Tool metadata: name, category, auth requirements, health status |
| `Event` | Timestamped, typed event with source, topic, and arbitrary payload |
| `Checkpoint` | Named snapshot of system state at a point in time |
| `Artifact` | Exportable output (markdown, JSON, HTML, binary) |
| `Session` | Container for a user session with start/end times and event history |

**Enums:**

| Enum | Values |
|---|---|
| `SessionState` | `IDLE`, `BOOTING`, `ONBOARDING`, `RUNNING`, `PAUSED`, `SHUTTING_DOWN` |
| `ToolHealth` | `HEALTHY`, `DEGRADED`, `UNHEALTHY`, `UNKNOWN` |
| `SafetyVerdict` | `ALLOW`, `DENY`, `WARN`, `REQUIRE_CONFIRMATION` |
| `EventTopic` | `SKILL`, `TOOL`, `GAME`, `SYSTEM`, `SAFETY`, `SESSION`, `ONBOARDING` |

### Event Bus (`event_bus.py`)

Lock-free async pub/sub built on `asyncio.Queue` and `collections.deque`.

**Design decisions:**
- **Bounded ring buffer** (default 10,000 events): Prevents unbounded memory growth. Oldest events are evicted when the buffer is full.
- **Topic-based filtering**: Subscribers can listen to specific `EventTopic` values or receive all events.
- **Replay support**: The entire buffer can be replayed to reconstruct state after a crash or for debugging.
- **No external dependencies**: Pure asyncio. No Redis, no RabbitMQ. The bus is in-process and designed for single-node operation.

**Key methods:**
- `emit(event)` — Publish an event. Delivered to all matching subscribers.
- `subscribe(callback, topics)` — Register a listener. Returns a subscription ID.
- `unsubscribe(sub_id)` — Remove a listener.
- `replay(callback)` — Replay all buffered events to a callback.

### Registry (`registry.py`)

A generic `Registry[T]` that provides:
- **Registration** with version tracking
- **Tag-based indexing** for fast filtering
- **Search** by name, tags, or custom predicates
- **Listing** with optional filters

Concrete registries:
- `SkillRegistry` (T = `SkillDefinition`)
- `ToolRegistry` (T = `ToolDefinition`)

The `CapabilityNegotiator` takes an agent manifest (a list of required capabilities) and returns a compatibility report against the current registry state.

### Safety Layer (`safety.py`)

Declarative rule engine. Rules are evaluated top-to-bottom by priority.

**Rule structure:**
```python
SafetyRule(
    name="block-rm-rf",
    pattern=r"rm\s+-rf\s+/",
    verdict=SafetyVerdict.DENY,
    message="Recursive root deletion blocked",
    priority=1,
)
```

**Default rules (7):**
1. Block recursive root deletion
2. Block private key access
3. Block `/etc/shadow` reads
4. Warn on environment variable access
5. Require confirmation for network downloads
6. Block crypto mining commands
7. Block fork bombs

All safety evaluations emit audit events to the bus.

### Kernel (`kernel.py`)

The central lifecycle manager. Owns:
- Boot sequence (initialize registries, load skills, register tools)
- Session management (create, checkpoint, restore)
- Event routing
- Safe execution wrapper (`execute_with_safety`)

**Lifecycle:**
```
boot() → onboard() → run() → [checkpoint() ↔ restore()] → shutdown()
```

---

## Skills (`src/skills/`)

### Loader (`engine/loader.py`)

Parses `Skill.md` files from disk. Each file uses YAML frontmatter:

```markdown
---
name: code-review
version: 1.0.0
tags: [code, quality, review]
parameters:
  - name: language
    type: string
    required: true
---

# Code Review

Review code for quality, bugs, and best practices...
```

The loader extracts frontmatter into a `SkillDefinition` and registers it with the `SkillRegistry`.

### Catalog (`catalog/generator.py`)

Contains the definitions for all 120 skills. The `generate_catalog()` function returns a list of `SkillDefinition` objects. The `generate_skill_md()` function writes a Skill.md file to disk for a given definition.

**Skill categories (13):**
- Code & Development (18 skills)
- Data & Analytics (12 skills)
- Security & Compliance (11 skills)
- DevOps & Infrastructure (10 skills)
- Documentation & Writing (12 skills)
- Research & Analysis (8 skills)
- Design & UI (6 skills)
- Project Management (8 skills)
- Communication (5 skills)
- Learning & Education (5 skills)
- System & Monitoring (8 skills)
- Games & Interactive (5 skills)
- Automation & Integration (12 skills)

---

## Tools (`src/tools/`)

### Catalog (`registry/catalog.py`)

54 tool definitions organized into 13 categories:

| Category | Count | Examples |
|---|---|---|
| Version Control | 6 | GitHub, GitLab, Bitbucket |
| CI/CD | 4 | GitHub Actions, Jenkins, CircleCI |
| Cloud | 5 | AWS, GCP, Azure, Vercel, Netlify |
| Database | 5 | PostgreSQL, MongoDB, Redis, SQLite |
| Communication | 5 | Slack, Discord, Teams, Email, Twilio |
| Monitoring | 4 | Datadog, Sentry, PagerDuty, Grafana |
| Documentation | 4 | Notion, Confluence, ReadTheDocs |
| Security | 4 | Snyk, Vault, SonarQube |
| Storage | 4 | S3, GCS, Dropbox, MinIO |
| Search | 3 | Elasticsearch, Algolia, Meilisearch |
| AI/ML | 4 | OpenAI, Anthropic, HuggingFace, Replicate |
| Productivity | 3 | Jira, Linear, Asana |
| Payment | 3 | Stripe, PayPal, Square |

Each tool definition includes: name, description, category, auth requirements (OAuth scopes), health check URL, and status.

### OAuth Manager (`oauth/manager.py`)

Full OAuth2 with PKCE implementation:
- Authorization URL generation with code challenge
- Token exchange
- Token storage (encrypted on disk)
- Automatic refresh before expiry
- Revocation

---

## Games (`src/games/`)

### Engine (`engine/`)

**GameState (`state.py`):**
- Undo/redo stacks with configurable depth
- Named checkpoints (create, restore, list, delete)
- State serialization for deterministic replay
- Delta computation between states

**GameRunner (`runner.py`):**
- `GameInterface` ABC that all games implement
- Meta-commands available in all games: `/undo`, `/redo`, `/save <name>`, `/load <name>`, `/saves`, `/restart`, `/help`, `/quit`
- Command routing: meta-commands handled by runner, game commands by the game

### D&D Quest Engine (`dnd/game.py`)

- 5 character classes with unique stat distributions
- Turn-based combat with initiative, attack rolls, damage, XP
- 5 encounter types: combat, puzzle, trap, treasure, boss
- Level-up system with stat improvements
- Rest/heal mechanics
- Character sheet display

### Adventure Engine (`adventure/game.py`)

- 3 branching story graphs (~64 nodes total)
- Choice tracking with numbered options
- Multiple endings per story
- Story-specific scoring
- Story selection at start

### Zork Engine (`zork/game.py`)

- 14 interconnected rooms with directional navigation
- Natural language parser: 50+ verb synonyms, preposition handling, fuzzy matching
- 14 items with weight, descriptions, and special behaviors
- 5 NPCs with dialogue, puzzles, and combat
- Dark rooms / grue mechanic
- Score and rank system
- Victory condition puzzle chain

---

## TUI (`src/tui/`)

Built on [Textual](https://textual.textualize.io/), the TUI is a keyboard-first terminal application.

### Components

| Component | File | Role |
|---|---|---|
| `HeaderBar` | `components/header.py` | Title, session state, skill/tool counts |
| `Sidebar` | `components/sidebar.py` | Tabbed browser: Skills, Tools, Games |
| `OutputPane` | `components/output_pane.py` | Primary output display |
| `EventLog` | `components/event_log.py` | Severity-colored live event stream |
| `InputBar` | `components/input_bar.py` | Command input with history |
| `StatusBar` | `components/status_bar.py` | Mode indicator, health, hints |

### Application (`app.py`)

`SuperMCPApp` composes all components, boots the kernel on mount, registers the three games, and subscribes to the event bus for live log updates. It routes slash commands to system handlers and non-slash input to the active game.

### Themes (`themes/default.py`)

A slate/violet/cyan/amber color palette with full Textual CSS for all components.

---

## Cross-Cutting Concerns

### Replay (`src/replay/engine.py`)

Captures events from the bus into `ReplayFrame` objects with sequence numbers, state deltas, and annotations. Frames are bundled into a `ReplayBundle` that can be exported to JSON and replayed at configurable speed.

### Analytics (`src/analytics/collector.py`)

Subscribes to the event bus and records `UsageRecord` entries for skills, tools, games, and actions. Generates aggregated `UsageReport` objects with top-N rankings, error rates, and average durations. Supports trend analysis by day.

### Observability (`src/observability/metrics.py`)

Three metric types:
- **Counter**: Monotonically increasing (skill invocations, errors, events)
- **Gauge**: Point-in-time value (active sessions, registered skills)
- **Histogram**: Distribution (skill duration, tool latency)

Plus OpenTelemetry-compatible `Span` objects for distributed tracing and a `trace()` async context manager.

Metrics export to Prometheus text format via `format_prometheus()`.

### Security Sandbox (`src/security/sandbox.py`)

Resource-limited command execution:
- Memory limit (default 256 MB)
- CPU time limit (default 30s)
- Output size limit (default 1 MB)
- Allowed/blocked command lists
- Path validation against allowed directories
- Timeout enforcement via `asyncio.wait_for`

### Artifact Exporter (`src/artifacts/exporter.py`)

Exports artifacts to disk in multiple formats (Markdown, JSON, HTML, plaintext, Python, binary). Supports session-level report generation as Markdown tables and arbitrary data export as JSON.

---

## Hook System (`src/api/hooks.py`)

The hook registry enables plugins to intercept system behavior without modifying core code.

**Hook lifecycle:**
1. Plugin registers hooks at specific points with a priority
2. When a hook point is triggered, all registered callbacks execute in priority order (ascending)
3. Callbacks are async and receive the hook point name plus arbitrary kwargs
4. Callbacks return `HookResult` with `allow` (bool), optional `modified_data`, and optional `message`
5. If any callback sets `allow=False`, the operation is blocked

**Categories:**
- Lifecycle (4 points)
- Skills (3 points)
- Tools (3 points)
- Events (2 points)
- Safety (2 points)
- Session (4 points)
- Games (3 points)
- Onboarding (3 points)
- Artifacts (1 point)

See [EXTENDING.md](EXTENDING.md) for the full plugin development guide.

---

## Data Flow

A typical skill invocation:

```
User input (TUI/CLI)
  → Kernel.execute_with_safety(action)
    → SafetyLayer.check(action) → emit(safety.check event)
      → [ALLOW] → HookRegistry.trigger("skill.invoke.before")
        → SkillRegistry.get(skill_id)
          → skill execution
            → HookRegistry.trigger("skill.invoke.after")
              → emit(skill.complete event)
                → AnalyticsCollector records usage
                → ReplayEngine captures frame
                → MetricsRegistry increments counter
                  → Result returned to user
```

Every arrow is an event. Every event is auditable.
