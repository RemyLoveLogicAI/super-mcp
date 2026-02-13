# ── Super-MCP Makefile ────────────────────────────────
# Developer ergonomics: every command is self-documenting.
# Run `make help` for the full list.
# ──────────────────────────────────────────────────────

.DEFAULT_GOAL := help
SHELL := /bin/bash
PYTHON := python3
VENV := .venv
BIN := $(VENV)/bin
PIP := $(BIN)/pip
PYTEST := $(BIN)/pytest
RUFF := $(BIN)/ruff
MYPY := $(BIN)/mypy
APP := $(BIN)/smcp

# Colours
CYAN  := \033[36m
GREEN := \033[32m
BOLD  := \033[1m
RESET := \033[0m

# ── Setup ────────────────────────────────────────────

.PHONY: venv
venv: ## Create virtual environment
	@echo "$(CYAN)Creating virtual environment…$(RESET)"
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	@echo "$(GREEN)✓ Virtual environment ready$(RESET)"

.PHONY: install
install: venv ## Install all dependencies (dev + production)
	@echo "$(CYAN)Installing dependencies…$(RESET)"
	$(PIP) install -e ".[dev]"
	@echo "$(GREEN)✓ All dependencies installed$(RESET)"

.PHONY: install-prod
install-prod: venv ## Install production dependencies only
	@echo "$(CYAN)Installing production dependencies…$(RESET)"
	$(PIP) install -e .
	@echo "$(GREEN)✓ Production dependencies installed$(RESET)"

# ── Running ──────────────────────────────────────────

.PHONY: tui
tui: ## Launch the TUI dashboard
	$(APP) tui

.PHONY: onboard
onboard: ## Run interactive onboarding
	$(APP) onboard

.PHONY: play
play: ## List available games
	$(APP) play --list

.PHONY: status
status: ## Show system status
	$(APP) status

.PHONY: metrics
metrics: ## Show live metrics
	$(APP) metrics

# ── Quality ──────────────────────────────────────────

.PHONY: lint
lint: ## Run linter (ruff)
	@echo "$(CYAN)Running ruff…$(RESET)"
	$(RUFF) check src/ tests/
	@echo "$(GREEN)✓ Lint passed$(RESET)"

.PHONY: lint-fix
lint-fix: ## Auto-fix lint issues
	$(RUFF) check --fix src/ tests/

.PHONY: format
format: ## Format code (ruff format)
	$(RUFF) format src/ tests/

.PHONY: format-check
format-check: ## Check formatting without changes
	$(RUFF) format --check src/ tests/

.PHONY: typecheck
typecheck: ## Run mypy strict type checking
	@echo "$(CYAN)Running mypy…$(RESET)"
	$(MYPY) src/
	@echo "$(GREEN)✓ Type check passed$(RESET)"

.PHONY: check
check: lint format-check typecheck ## Run all static checks

# ── Testing ──────────────────────────────────────────

.PHONY: test
test: ## Run test suite
	@echo "$(CYAN)Running tests…$(RESET)"
	$(PYTEST) tests/ -v --tb=short
	@echo "$(GREEN)✓ Tests passed$(RESET)"

.PHONY: test-fast
test-fast: ## Run tests (no slow markers)
	$(PYTEST) tests/ -v --tb=short -m "not slow"

.PHONY: test-cov
test-cov: ## Run tests with coverage report
	$(PYTEST) tests/ -v --tb=short \
		--cov=src --cov-report=term-missing --cov-report=html
	@echo "$(GREEN)✓ Coverage report at htmlcov/index.html$(RESET)"

.PHONY: test-watch
test-watch: ## Run tests in watch mode (requires pytest-watch)
	$(BIN)/ptw -- -v --tb=short

# ── Docker ───────────────────────────────────────────

.PHONY: docker-build
docker-build: ## Build production Docker image
	@echo "$(CYAN)Building Docker image…$(RESET)"
	docker build -t super-mcp:latest .
	@echo "$(GREEN)✓ Image built: super-mcp:latest$(RESET)"

.PHONY: docker-run
docker-run: ## Run container (detached)
	docker compose up -d
	@echo "$(GREEN)✓ Running at http://localhost:9090$(RESET)"

.PHONY: docker-stop
docker-stop: ## Stop container
	docker compose down

.PHONY: docker-logs
docker-logs: ## Tail container logs
	docker compose logs -f super-mcp

.PHONY: docker-shell
docker-shell: ## Open shell in running container
	docker compose exec super-mcp /bin/sh

# ── Maintenance ──────────────────────────────────────

.PHONY: clean
clean: ## Remove build artifacts and caches
	@echo "$(CYAN)Cleaning…$(RESET)"
	rm -rf build/ dist/ *.egg-info .eggs/
	rm -rf .mypy_cache/ .ruff_cache/ .pytest_cache/
	rm -rf htmlcov/ .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Clean$(RESET)"

.PHONY: clean-all
clean-all: clean ## Remove everything including venv
	rm -rf $(VENV)
	@echo "$(GREEN)✓ Full clean (including venv)$(RESET)"

.PHONY: update
update: ## Update all dependencies
	$(PIP) install --upgrade -e ".[dev]"
	@echo "$(GREEN)✓ Dependencies updated$(RESET)"

# ── Skills ───────────────────────────────────────────

.PHONY: skills-list
skills-list: ## List all loaded skills
	$(APP) skills --list

.PHONY: skills-generate
skills-generate: ## Generate skill stubs from templates
	$(APP) generate-skills

.PHONY: export-report
export-report: ## Export system report (Markdown)
	$(APP) export-report --format md --output report.md
	@echo "$(GREEN)✓ Report exported to report.md$(RESET)"

# ── CI Helpers ───────────────────────────────────────

.PHONY: ci
ci: check test ## Full CI pipeline (lint + typecheck + test)

.PHONY: ci-docker
ci-docker: docker-build ## CI: build Docker image
	docker run --rm super-mcp:latest smcp status

# ── Help ─────────────────────────────────────────────

.PHONY: help
help: ## Show this help
	@echo ""
	@echo "$(BOLD)Super-MCP$(RESET) — development commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-18s$(RESET) %s\n", $$1, $$2}'
	@echo ""
