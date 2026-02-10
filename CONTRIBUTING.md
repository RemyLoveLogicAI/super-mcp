# Contributing to Super-MCP

Thank you for your interest in contributing. This guide covers the workflow, standards, and conventions used in this project.

---

## Getting Started

### Prerequisites

- Python 3.11 or later
- Git

### Setup

```bash
git clone https://github.com/super-mcp/super-mcp.git
cd super-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Verify

```bash
smcp status
pytest
ruff check src/
```

---

## Development Workflow

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make changes** in `src/` and add tests in `tests/`.

3. **Run checks**:
   ```bash
   ruff check src/              # Lint
   ruff format src/              # Format
   mypy src/                     # Type check
   pytest                        # Test
   ```

4. **Commit** with a descriptive message:
   ```bash
   git commit -m "feat: add XYZ skill with parameter validation"
   ```

5. **Push** and open a pull request against `main`.

---

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use |
|---|---|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation only |
| `test:` | Adding or fixing tests |
| `refactor:` | Code restructuring (no behavior change) |
| `perf:` | Performance improvement |
| `chore:` | Tooling, CI, dependency updates |

---

## Code Standards

### Style

- **Formatter**: Ruff (line length 100)
- **Linter**: Ruff with an extended rule set (see `pyproject.toml`)
- **Type checker**: mypy in strict mode
- **Imports**: Sorted by isort (via Ruff), `src` as first-party

### Conventions

- All public functions have docstrings
- All modules have module-level docstrings
- Pydantic v2 models for all data structures
- Async by default for I/O-bound operations
- `structlog` for structured logging
- No mutable default arguments
- No bare `except:` clauses

### Testing

- Test files mirror the source tree: `src/kernel/safety.py` → `tests/unit/test_safety.py`
- Use `pytest-asyncio` for async tests
- Fixtures go in `conftest.py` at the appropriate level
- Mark slow tests with `@pytest.mark.slow`
- Mark integration tests with `@pytest.mark.integration`

---

## Project Structure

```
src/
├── kernel/        # Core types, event bus, registries, safety, kernel
├── skills/        # Skill loader and catalog
├── tools/         # Tool registry and OAuth
├── onboarding/    # Onboarding wizard
├── games/         # Game engine and 3 games
├── tui/           # Terminal UI
├── replay/        # Replay engine
├── analytics/     # Usage analytics
├── observability/ # Metrics and tracing
├── artifacts/     # Export system
├── security/      # Sandbox
└── api/           # Hook registry
```

### Adding a Module

1. Create the directory under `src/`
2. Add an `__init__.py` with public exports
3. Wire it into the kernel or CLI as appropriate
4. Add tests in the corresponding `tests/` subdirectory

---

## Adding Skills

See [EXTENDING.md](EXTENDING.md#writing-a-custom-skill) for the Skill.md format.

Quick checklist:
- [ ] File placed in `skills/` with `.md` extension
- [ ] YAML frontmatter includes `name`, `version`, `tags`
- [ ] Name is kebab-case and unique
- [ ] At least one example in frontmatter
- [ ] Body contains clear instructions

---

## Adding Tools

See [EXTENDING.md](EXTENDING.md#writing-a-custom-tool) for the ToolDefinition pattern.

Quick checklist:
- [ ] `ToolDefinition` created with all required fields
- [ ] Category assigned from existing categories (or propose a new one)
- [ ] Health check URL provided
- [ ] OAuth scopes documented if auth is required
- [ ] Added to `src/tools/registry/catalog.py`

---

## Adding Games

See [EXTENDING.md](EXTENDING.md#writing-a-custom-game) for the GameInterface ABC.

Quick checklist:
- [ ] Implements all `GameInterface` methods
- [ ] `_get_state()` captures all mutable state
- [ ] `_restore_state()` fully restores from captured state
- [ ] Handles unknown commands gracefully
- [ ] Registered in `src/tui/app.py` and `src/tui/components/sidebar.py`
- [ ] Tests cover initialization, input processing, state save/restore

---

## Pull Request Guidelines

- One logical change per PR
- PR title follows the commit message format
- Description explains what changed and why
- All CI checks pass
- New features include tests
- New modules include `__init__.py` with exports
- No commented-out code
- No unused imports

---

## Reporting Issues

Open a GitHub issue with:
- Python version
- OS and terminal emulator
- Steps to reproduce
- Expected vs actual behavior
- Full error traceback (if applicable)

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
