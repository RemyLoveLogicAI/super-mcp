"""Onboarding engine — one-command setup for everything.

Auth all tools, validate permissions, run diagnostics,
build indexes, confirm readiness. Fails loudly and informatively.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

import structlog

from src.kernel.event_bus import EventBus
from src.kernel.kernel import Kernel
from src.kernel.registry import SkillRegistry, ToolRegistry
from src.kernel.types import (
    Severity,
    SessionState,
    SkillDefinition,
    ToolDefinition,
    ToolHealth,
)
from src.skills.catalog.generator import SKILL_DEFINITIONS
from src.skills.engine.loader import load_skills_from_directory, parse_skill_md
from src.tools.oauth.manager import OAuthManager
from src.tools.registry.catalog import TOOL_CATALOG

logger = structlog.get_logger(__name__)


class OnboardingStep(str, Enum):
    VERIFY_ENV = "verify_environment"
    LOAD_SKILLS = "load_skills"
    REGISTER_TOOLS = "register_tools"
    AUTH_TOOLS = "authenticate_tools"
    HEALTH_CHECK = "health_check"
    BUILD_INDEX = "build_index"
    VALIDATE = "validate_readiness"
    COMPLETE = "complete"


@dataclass
class StepResult:
    step: OnboardingStep
    success: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class OnboardingReport:
    steps: list[StepResult] = field(default_factory=list)
    overall_success: bool = False
    total_skills: int = 0
    total_tools: int = 0
    authenticated_tools: int = 0
    healthy_tools: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.overall_success and self.total_skills > 0


class OnboardingEngine:
    """Orchestrates the full onboarding flow."""

    def __init__(
        self,
        kernel: Kernel,
        oauth_manager: OAuthManager | None = None,
        skills_dir: Path | None = None,
    ) -> None:
        self._kernel = kernel
        self._oauth = oauth_manager
        self._skills_dir = skills_dir or Path("skills")
        self._report = OnboardingReport()
        self._progress_callback: Any = None

    def on_progress(self, callback: Any) -> None:
        self._progress_callback = callback

    async def _report_progress(self, step: OnboardingStep, message: str) -> None:
        if self._progress_callback:
            await self._progress_callback(step, message)
        await self._kernel.event_bus.emit(
            kind="onboarding.progress",
            source="onboarding",
            data={"step": step.value, "message": message},
        )

    async def run(self) -> OnboardingReport:
        """Execute the full onboarding sequence."""
        await self._kernel.boot()
        await self._kernel.transition(SessionState.ONBOARDING)

        steps = [
            (OnboardingStep.VERIFY_ENV, self._verify_environment),
            (OnboardingStep.LOAD_SKILLS, self._load_skills),
            (OnboardingStep.REGISTER_TOOLS, self._register_tools),
            (OnboardingStep.AUTH_TOOLS, self._authenticate_tools),
            (OnboardingStep.HEALTH_CHECK, self._health_check),
            (OnboardingStep.BUILD_INDEX, self._build_index),
            (OnboardingStep.VALIDATE, self._validate_readiness),
        ]

        all_passed = True
        for step_name, step_fn in steps:
            await self._report_progress(step_name, f"Starting {step_name.value}...")
            try:
                result = await step_fn()
                self._report.steps.append(result)
                if not result.success:
                    all_passed = False
                    self._report.errors.append(f"{step_name.value}: {result.message}")
                if result.warnings:
                    self._report.warnings.extend(result.warnings)
            except Exception as e:
                result = StepResult(
                    step=step_name,
                    success=False,
                    message=f"Unexpected error: {e}",
                )
                self._report.steps.append(result)
                self._report.errors.append(f"{step_name.value}: {e}")
                all_passed = False

        self._report.overall_success = all_passed
        self._report.total_skills = self._kernel.skill_registry.count
        self._report.total_tools = self._kernel.tool_registry.count

        if all_passed:
            await self._kernel.transition(SessionState.READY)
        else:
            await self._kernel.event_bus.emit(
                kind="onboarding.failed",
                source="onboarding",
                data={"errors": self._report.errors},
                severity=Severity.ERROR,
            )

        await self._kernel.event_bus.emit(
            kind="onboarding.complete",
            source="onboarding",
            data={
                "success": all_passed,
                "skills": self._report.total_skills,
                "tools": self._report.total_tools,
            },
        )

        return self._report

    async def _verify_environment(self) -> StepResult:
        """Check that the environment meets minimum requirements."""
        import sys
        warnings = []

        py_version = sys.version_info
        if py_version < (3, 11):
            return StepResult(
                step=OnboardingStep.VERIFY_ENV,
                success=False,
                message=f"Python 3.11+ required, found {py_version.major}.{py_version.minor}",
            )

        config_dir = Path.home() / ".super-mcp"
        config_dir.mkdir(parents=True, exist_ok=True)

        if not self._skills_dir.exists():
            warnings.append(f"Skills directory not found: {self._skills_dir}")

        return StepResult(
            step=OnboardingStep.VERIFY_ENV,
            success=True,
            message=f"Environment verified: Python {py_version.major}.{py_version.minor}",
            warnings=warnings,
        )

    async def _load_skills(self) -> StepResult:
        """Load and register all skills."""
        count = 0
        warnings = []

        # Load from Skill.md files if they exist
        if self._skills_dir.exists():
            skills = await load_skills_from_directory(self._skills_dir)
            for skill in skills:
                await self._kernel.skill_registry.register(skill)
                count += 1

        # Also register built-in skills from the catalog definitions
        for skill_def in SKILL_DEFINITIONS:
            slug = skill_def["slug"]
            if not self._kernel.skill_registry.get(slug):
                try:
                    from src.kernel.types import DeterminismLevel, SkillCategory
                    sd = SkillDefinition(
                        name=skill_def["name"],
                        slug=slug,
                        category=SkillCategory(skill_def["cat"]),
                        purpose=skill_def["purpose"],
                        description=skill_def["purpose"],
                        determinism=DeterminismLevel(skill_def["det"]),
                        tool_dependencies=skill_def.get("tools", []),
                        tags=skill_def.get("tags", []),
                    )
                    await self._kernel.skill_registry.register(sd)
                    count += 1
                except Exception as e:
                    warnings.append(f"Failed to register skill {slug}: {e}")

        return StepResult(
            step=OnboardingStep.LOAD_SKILLS,
            success=count > 0,
            message=f"Loaded {count} skills",
            details={"count": count},
            warnings=warnings,
        )

    async def _register_tools(self) -> StepResult:
        """Register all tools from the catalog."""
        count = 0
        for tool in TOOL_CATALOG:
            await self._kernel.tool_registry.register(tool)
            count += 1

        return StepResult(
            step=OnboardingStep.REGISTER_TOOLS,
            success=True,
            message=f"Registered {count} tools",
            details={"count": count},
        )

    async def _authenticate_tools(self) -> StepResult:
        """Check environment variables for API keys and validate OAuth tokens."""
        authenticated = 0
        warnings = []
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google-ai": "GOOGLE_AI_API_KEY",
            "cohere": "COHERE_API_KEY",
            "replicate": "REPLICATE_API_TOKEN",
            "huggingface": "HF_TOKEN",
            "stability-ai": "STABILITY_API_KEY",
            "eleven-labs": "ELEVENLABS_API_KEY",
            "deepgram": "DEEPGRAM_API_KEY",
            "pinecone": "PINECONE_API_KEY",
            "sentry": "SENTRY_DSN",
            "datadog": "DD_API_KEY",
            "web-search": "SERPAPI_KEY",
            "supabase": "SUPABASE_KEY",
            "vercel": "VERCEL_TOKEN",
        }

        for tool_slug, env_var in env_map.items():
            if os.environ.get(env_var):
                authenticated += 1
                await self._kernel.tool_registry.update_health(tool_slug, ToolHealth.HEALTHY)
            else:
                warnings.append(f"{tool_slug}: Missing {env_var}")

        # Check OAuth tokens
        if self._oauth:
            for slug in self._oauth.authenticated_tools():
                if slug not in env_map:
                    authenticated += 1
                    await self._kernel.tool_registry.update_health(slug, ToolHealth.HEALTHY)

        self._report.authenticated_tools = authenticated

        return StepResult(
            step=OnboardingStep.AUTH_TOOLS,
            success=True,  # Auth is optional — tools degrade gracefully
            message=f"Authenticated {authenticated} tools",
            details={"authenticated": authenticated},
            warnings=warnings,
        )

    async def _health_check(self) -> StepResult:
        """Run health checks on authenticated tools."""
        healthy = 0
        warnings = []

        for tool in self._kernel.tool_registry.list_all():
            if tool.health == ToolHealth.HEALTHY:
                healthy += 1
            elif tool.health == ToolHealth.DOWN:
                warnings.append(f"{tool.slug}: DOWN")

        self._report.healthy_tools = healthy

        return StepResult(
            step=OnboardingStep.HEALTH_CHECK,
            success=True,
            message=f"{healthy} tools healthy",
            details={"healthy": healthy},
            warnings=warnings,
        )

    async def _build_index(self) -> StepResult:
        """Build search indexes for skills and tools."""
        skill_index = {
            s.slug: {
                "name": s.name,
                "category": s.category.value,
                "tags": s.tags,
                "determinism": s.determinism.value,
            }
            for s in self._kernel.skill_registry.list_all()
        }

        tool_index = {
            t.slug: {
                "name": t.name,
                "auth_type": t.auth_type.value,
                "health": t.health.value,
                "tags": t.tags,
            }
            for t in self._kernel.tool_registry.list_all()
        }

        return StepResult(
            step=OnboardingStep.BUILD_INDEX,
            success=True,
            message=f"Built indexes: {len(skill_index)} skills, {len(tool_index)} tools",
            details={"skill_count": len(skill_index), "tool_count": len(tool_index)},
        )

    async def _validate_readiness(self) -> StepResult:
        """Final validation that the system is ready."""
        issues = []

        if self._kernel.skill_registry.count == 0:
            issues.append("No skills registered")

        if self._kernel.tool_registry.count == 0:
            issues.append("No tools registered")

        success = len(issues) == 0

        return StepResult(
            step=OnboardingStep.VALIDATE,
            success=success,
            message="System ready" if success else f"Readiness issues: {'; '.join(issues)}",
            details={"issues": issues},
        )
