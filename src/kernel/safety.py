"""Safety and rule enforcement layer.

Every action passes through the safety layer before execution.
Rules are declarative, composable, and auditable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import structlog

from src.kernel.event_bus import EventBus
from src.kernel.types import Event, Severity

logger = structlog.get_logger(__name__)


class RuleVerdict(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    WARN = "warn"
    REQUIRE_CONFIRMATION = "require_confirmation"


@dataclass(frozen=True)
class SafetyRule:
    """A single declarative safety rule."""
    id: str
    name: str
    description: str
    pattern: str  # regex pattern to match against action descriptions
    verdict: RuleVerdict
    priority: int = 0  # higher = evaluated first
    enabled: bool = True

    def matches(self, action_description: str) -> bool:
        if not self.enabled:
            return False
        return bool(re.search(self.pattern, action_description, re.IGNORECASE))


@dataclass
class SafetyEvaluation:
    """Result of evaluating an action against all rules."""
    action: str
    verdict: RuleVerdict
    triggered_rules: list[SafetyRule]
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.verdict in (RuleVerdict.ALLOW, RuleVerdict.WARN)


# Default safety rules
DEFAULT_RULES: list[SafetyRule] = [
    SafetyRule(
        id="no-destructive-system",
        name="Block destructive system operations",
        description="Prevent rm -rf, format, and similar destructive commands",
        pattern=r"(rm\s+-rf\s+/|format\s+|mkfs|dd\s+if=.*of=/dev)",
        verdict=RuleVerdict.DENY,
        priority=100,
    ),
    SafetyRule(
        id="no-credential-exposure",
        name="Block credential exposure",
        description="Prevent logging or transmitting secrets/tokens/passwords",
        pattern=r"(password|secret|token|api.?key).*?(log|print|send|post|transmit)",
        verdict=RuleVerdict.DENY,
        priority=99,
    ),
    SafetyRule(
        id="warn-network-access",
        name="Warn on external network calls",
        description="Flag when a skill attempts external network access",
        pattern=r"(http[s]?://|fetch|request|curl|wget)",
        verdict=RuleVerdict.WARN,
        priority=50,
    ),
    SafetyRule(
        id="confirm-file-write",
        name="Confirm file writes outside project",
        description="Require confirmation for writes outside the project directory",
        pattern=r"(write|save|create).*?(/etc/|/usr/|/var/|/home/|~/\.)",
        verdict=RuleVerdict.REQUIRE_CONFIRMATION,
        priority=80,
    ),
    SafetyRule(
        id="no-infinite-loops",
        name="Block unbounded loops",
        description="Prevent actions that could cause infinite loops",
        pattern=r"(while\s+true|for\s*\(\s*;\s*;\s*\)|infinite|unbounded)",
        verdict=RuleVerdict.DENY,
        priority=90,
    ),
    SafetyRule(
        id="warn-large-output",
        name="Warn on large outputs",
        description="Flag when an action may produce very large outputs",
        pattern=r"(dump|export|backup).*?(all|entire|full|complete)",
        verdict=RuleVerdict.WARN,
        priority=40,
    ),
    SafetyRule(
        id="no-privilege-escalation",
        name="Block privilege escalation",
        description="Prevent sudo, su, and chmod 777",
        pattern=r"(sudo\s+|su\s+-|chmod\s+777|chown\s+root)",
        verdict=RuleVerdict.DENY,
        priority=95,
    ),
]


class SafetyLayer:
    """Evaluates actions against safety rules and emits audit events."""

    def __init__(self, event_bus: EventBus, rules: list[SafetyRule] | None = None) -> None:
        self._bus = event_bus
        self._rules = sorted(
            rules or list(DEFAULT_RULES),
            key=lambda r: -r.priority,
        )
        self._evaluation_count = 0
        self._deny_count = 0

    async def evaluate(self, action: str, context: dict[str, Any] | None = None) -> SafetyEvaluation:
        """Evaluate an action string against all safety rules."""
        self._evaluation_count += 1
        triggered: list[SafetyRule] = []
        warnings: list[str] = []
        verdict = RuleVerdict.ALLOW

        for rule in self._rules:
            if rule.matches(action):
                triggered.append(rule)
                if rule.verdict == RuleVerdict.DENY:
                    verdict = RuleVerdict.DENY
                    break
                elif rule.verdict == RuleVerdict.REQUIRE_CONFIRMATION:
                    if verdict != RuleVerdict.DENY:
                        verdict = RuleVerdict.REQUIRE_CONFIRMATION
                elif rule.verdict == RuleVerdict.WARN:
                    warnings.append(f"[{rule.id}] {rule.description}")
                    if verdict == RuleVerdict.ALLOW:
                        verdict = RuleVerdict.WARN

        evaluation = SafetyEvaluation(
            action=action,
            verdict=verdict,
            triggered_rules=triggered,
            warnings=warnings,
            metadata=context or {},
        )

        if verdict == RuleVerdict.DENY:
            self._deny_count += 1
            await self._bus.emit(
                kind="safety.denied",
                source="safety_layer",
                data={
                    "action": action,
                    "rules": [r.id for r in triggered],
                },
                severity=Severity.WARN,
            )
        elif verdict == RuleVerdict.REQUIRE_CONFIRMATION:
            await self._bus.emit(
                kind="safety.confirmation_required",
                source="safety_layer",
                data={
                    "action": action,
                    "rules": [r.id for r in triggered],
                },
                severity=Severity.INFO,
            )

        return evaluation

    def add_rule(self, rule: SafetyRule) -> None:
        self._rules.append(rule)
        self._rules.sort(key=lambda r: -r.priority)

    def remove_rule(self, rule_id: str) -> bool:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.id != rule_id]
        return len(self._rules) < before

    @property
    def stats(self) -> dict[str, int]:
        return {
            "total_evaluations": self._evaluation_count,
            "total_denials": self._deny_count,
            "active_rules": len([r for r in self._rules if r.enabled]),
        }
