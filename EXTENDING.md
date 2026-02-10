# Extending Super-MCP

This guide covers how to extend Super-MCP with custom skills, tools, games, and plugins.

---

## Table of Contents

1. [Writing a Custom Skill](#writing-a-custom-skill)
2. [Writing a Custom Tool](#writing-a-custom-tool)
3. [Writing a Custom Game](#writing-a-custom-game)
4. [Writing a Plugin (Hooks)](#writing-a-plugin)
5. [Hook Reference](#hook-reference)
6. [Best Practices](#best-practices)

---

## Writing a Custom Skill

Skills are Markdown files with YAML frontmatter. To add a skill:

### 1. Create the Skill.md file

```markdown
---
name: my-custom-skill
version: 1.0.0
tags: [custom, example]
parameters:
  - name: input_text
    type: string
    required: true
    description: The text to process
  - name: format
    type: string
    required: false
    default: markdown
    description: Output format
examples:
  - input: "Analyze this code"
    output: "Code analysis report..."
---

# My Custom Skill

Description of what the skill does and when to use it.

## Instructions

Step-by-step instructions for the agent executing this skill.

## Output Format

Describe the expected output structure.
```

### 2. Place it in the skills directory

```bash
cp my-custom-skill.md skills/
```

### 3. It will be auto-loaded

The skill loader scans the `skills/` directory at boot and registers every `.md` file with valid frontmatter.

### Skill Definition Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Unique identifier (kebab-case) |
| `version` | string | yes | Semantic version |
| `tags` | list[str] | yes | Categorization tags |
| `parameters` | list[dict] | no | Input parameters |
| `examples` | list[dict] | no | Input/output examples |

---

## Writing a Custom Tool

Tools are registered programmatically via `ToolDefinition` objects.

### 1. Define the tool

```python
from src.kernel.types import ToolDefinition, ToolHealth

my_tool = ToolDefinition(
    name="my-api",
    description="Connects to My API for data retrieval",
    category="custom",
    auth_required=True,
    auth_scopes=["read", "write"],
    health_check_url="https://api.example.com/health",
    health=ToolHealth.UNKNOWN,
    version="1.0.0",
    tags=["custom", "api"],
)
```

### 2. Register it with the kernel

```python
kernel = Kernel()
await kernel.boot()
kernel.tool_registry.register(my_tool)
```

### 3. Configure OAuth (if required)

```python
from src.tools.oauth.manager import OAuthManager

oauth = OAuthManager()
oauth.register_provider(
    name="my-api",
    client_id="your-client-id",
    client_secret="your-client-secret",
    authorize_url="https://api.example.com/oauth/authorize",
    token_url="https://api.example.com/oauth/token",
    scopes=["read", "write"],
)
```

---

## Writing a Custom Game

Games implement the `GameInterface` abstract base class.

### 1. Implement GameInterface

```python
from src.games.engine.runner import GameInterface

class MyGame(GameInterface):
    @property
    def game_type(self) -> str:
        return "my-game"

    async def initialize(self) -> str:
        """Return the opening text."""
        self._score = 0
        return "Welcome to My Game! Type 'help' for commands."

    async def process_input(self, user_input: str) -> str:
        """Process a command and return the response."""
        cmd = user_input.strip().lower()
        if cmd == "help":
            return self.get_help()
        if cmd == "score":
            return f"Score: {self._score}"
        return f"You said: {user_input}"

    def get_help(self) -> str:
        return "Commands: help, score, quit"

    def validate_input(self, user_input: str) -> bool:
        return len(user_input.strip()) > 0

    def generate_summary(self) -> str:
        return f"Game over. Final score: {self._score}"

    def _get_state(self) -> dict:
        """Return serializable state for checkpoints."""
        return {"score": self._score}

    def _restore_state(self, state: dict) -> None:
        """Restore from a checkpoint."""
        self._score = state.get("score", 0)
```

### 2. Register with the GameRunner

```python
from src.games.engine.runner import GameRunner
from src.games.engine.state import GameState

runner = GameRunner()
runner.register_game("my-game", MyGame)

# Start the game
opening = await runner.start_game("my-game")
print(opening)

# Process input
response = await runner.process_input("help")
print(response)
```

### 3. Register with the TUI (optional)

To make the game appear in the TUI sidebar, add it to the game launcher list in `src/tui/components/sidebar.py` and register it in `src/tui/app.py`.

### State Management

The `GameRunner` wraps your game with full state management:

- **Undo/Redo**: Every `process_input` call creates a state snapshot. Users can `/undo` and `/redo`.
- **Checkpoints**: Named save points via `/save <name>` and `/load <name>`.
- **Restart**: Full game reset via `/restart`.

Your game only needs to implement `_get_state()` and `_restore_state()`. The runner handles the rest.

---

## Writing a Plugin

Plugins use the hook system to intercept and modify system behavior.

### 1. Define hook callbacks

```python
from src.api.hooks import HookResult

async def on_skill_invoke(hook_point: str, **kwargs) -> HookResult:
    """Log every skill invocation."""
    skill_name = kwargs.get("skill_name", "unknown")
    print(f"[MyPlugin] Skill invoked: {skill_name}")
    return HookResult(allow=True)

async def on_safety_check(hook_point: str, **kwargs) -> HookResult:
    """Block a specific action."""
    action = kwargs.get("action", "")
    if "dangerous_command" in action:
        return HookResult(
            allow=False,
            message="Blocked by MyPlugin: dangerous command detected",
        )
    return HookResult(allow=True)
```

### 2. Register the plugin

```python
from src.api.hooks import HookRegistry

registry = HookRegistry()

# Register the plugin (groups hooks for management)
registry.register_plugin(
    plugin_id="my-plugin",
    hooks={
        "skill.invoke.before": on_skill_invoke,
        "safety.check.before": on_safety_check,
    },
    priority=50,  # Lower number = higher priority
)
```

### 3. Hook execution order

1. Hooks are sorted by priority (ascending). Priority 1 runs before priority 100.
2. Each hook receives the hook point name and keyword arguments.
3. Each hook returns a `HookResult`:
   - `allow=True` — Continue to the next hook
   - `allow=False` — Block the operation (remaining hooks are skipped)
   - `modified_data` — Optional dict merged into the operation context
   - `message` — Optional message logged or shown to the user
4. If any hook blocks, the operation is aborted with the blocking message.

### 4. Unregister when done

```python
registry.unregister_plugin("my-plugin")
```

---

## Hook Reference

### Lifecycle Hooks

| Hook Point | Trigger | kwargs |
|---|---|---|
| `kernel.boot.before` | Before kernel initialization | `config` |
| `kernel.boot.after` | After kernel is ready | `kernel` |
| `kernel.shutdown.before` | Before shutdown begins | `reason` |
| `kernel.shutdown.after` | After shutdown completes | `duration_ms` |

### Skill Hooks

| Hook Point | Trigger | kwargs |
|---|---|---|
| `skill.register.before` | Before a skill is registered | `skill_definition` |
| `skill.invoke.before` | Before a skill executes | `skill_name`, `parameters` |
| `skill.invoke.after` | After a skill completes | `skill_name`, `result`, `duration_ms` |

### Tool Hooks

| Hook Point | Trigger | kwargs |
|---|---|---|
| `tool.register.before` | Before a tool is registered | `tool_definition` |
| `tool.invoke.before` | Before a tool executes | `tool_name`, `action` |
| `tool.invoke.after` | After a tool completes | `tool_name`, `result`, `duration_ms` |
| `tool.health_check.after` | After a health check runs | `tool_name`, `health` |

### Event Hooks

| Hook Point | Trigger | kwargs |
|---|---|---|
| `event.emit.before` | Before an event is published | `event` |
| `event.subscribe.before` | Before a subscription is created | `topics`, `callback` |

### Safety Hooks

| Hook Point | Trigger | kwargs |
|---|---|---|
| `safety.check.before` | Before a safety rule is evaluated | `action`, `context` |
| `safety.violation.after` | After a safety violation is detected | `rule`, `action`, `verdict` |

### Session Hooks

| Hook Point | Trigger | kwargs |
|---|---|---|
| `session.start.before` | Before a session begins | `session_id` |
| `session.start.after` | After a session is active | `session` |
| `session.end.before` | Before a session ends | `session_id`, `reason` |
| `session.end.after` | After a session is closed | `session_id`, `duration_ms` |

### Game Hooks

| Hook Point | Trigger | kwargs |
|---|---|---|
| `game.start.before` | Before a game initializes | `game_type` |
| `game.input.before` | Before game input is processed | `game_type`, `input` |
| `game.end.after` | After a game concludes | `game_type`, `summary` |

### Onboarding Hooks

| Hook Point | Trigger | kwargs |
|---|---|---|
| `onboard.start.before` | Before onboarding begins | `config` |
| `onboard.step.after` | After an onboarding step completes | `step_name`, `result` |
| `onboard.complete.after` | After onboarding finishes | `results` |

### Artifact Hooks

| Hook Point | Trigger | kwargs |
|---|---|---|
| `artifact.export.before` | Before an artifact is written to disk | `artifact`, `path`, `format` |

---

## Best Practices

### Skills

- Use descriptive, kebab-case names: `code-review`, not `CodeReview`
- Include at least 2 examples in frontmatter
- Tag broadly: a security skill should have both `security` and its specific domain tag
- Write clear instructions — the skill body is what the agent reads

### Tools

- Always set a `health_check_url` so the system can verify connectivity
- Use the narrowest OAuth scopes possible
- Set `auth_required=False` for tools that support anonymous access

### Games

- Keep `_get_state()` / `_restore_state()` pure and complete — if a field is mutable, it must be captured
- Return clear, descriptive text from `process_input()` — no empty strings
- Always handle unknown commands gracefully ("I don't understand that")

### Plugins

- Use priority 50 as default. Reserve 1–10 for security plugins, 90–100 for logging
- Keep hooks fast — they run synchronously in the pipeline
- Always return `HookResult(allow=True)` unless you intentionally want to block
- Clean up: call `unregister_plugin()` when your plugin is no longer needed
- Use `plugin_id` to namespace your hooks for easy management
