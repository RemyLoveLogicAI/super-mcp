"""Core type system for Super-MCP.

Every entity in the system traces back to these types. They enforce
structural contracts at the boundary and let internal code stay loose.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Literal, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DeterminismLevel(str, Enum):
    """How predictable a skill's output is."""
    DETERMINISTIC = "deterministic"
    QUASI_DETERMINISTIC = "quasi_deterministic"
    GENERATIVE = "generative"


class Severity(str, Enum):
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"


class ToolAuthType(str, Enum):
    NONE = "none"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BEARER = "bearer"
    BASIC = "basic"
    CUSTOM = "custom"


class ToolHealth(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class SkillCategory(str, Enum):
    CODING = "coding"
    WRITING = "writing"
    ANALYSIS = "analysis"
    DATA = "data"
    DEVOPS = "devops"
    SECURITY = "security"
    DESIGN = "design"
    COMMUNICATION = "communication"
    RESEARCH = "research"
    AUTOMATION = "automation"
    GAMES = "games"
    PRODUCTIVITY = "productivity"
    EDUCATION = "education"
    CREATIVE = "creative"
    SYSTEM = "system"


class GameType(str, Enum):
    DND = "dnd"
    ADVENTURE = "adventure"
    ZORK = "zork"


class SessionState(str, Enum):
    INITIALIZING = "initializing"
    ONBOARDING = "onboarding"
    READY = "ready"
    ACTIVE = "active"
    PAUSED = "paused"
    GAME = "game"
    TERMINATED = "terminated"


class ArtifactFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"
    PDF = "pdf"
    HTML = "html"
    YAML = "yaml"
    PLAIN = "plain"


# ---------------------------------------------------------------------------
# Core Identity
# ---------------------------------------------------------------------------

class EntityID(BaseModel):
    """Universal identifier for any system entity."""
    id: UUID = Field(default_factory=uuid4)
    kind: str
    namespace: str = "default"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def qualified(self) -> str:
        return f"{self.namespace}:{self.kind}:{self.id}"

    def fingerprint(self) -> str:
        return hashlib.sha256(self.qualified.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Capability Negotiation
# ---------------------------------------------------------------------------

class Capability(BaseModel):
    """A single capability an agent or tool exposes."""
    name: str
    version: str = "1.0.0"
    required: bool = False
    parameters: dict[str, Any] = Field(default_factory=dict)


class CapabilityManifest(BaseModel):
    """What an agent brings to the table."""
    agent_id: str
    agent_version: str
    capabilities: list[Capability] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)

    def supports(self, name: str) -> bool:
        return any(c.name == name for c in self.capabilities)

    def negotiate(self, required: list[Capability]) -> tuple[bool, list[str]]:
        """Return (all_met, list_of_missing)."""
        missing = []
        for req in required:
            if req.required and not self.supports(req.name):
                missing.append(req.name)
        return len(missing) == 0, missing


# ---------------------------------------------------------------------------
# Skill Schema
# ---------------------------------------------------------------------------

class SkillInput(BaseModel):
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


class SkillOutput(BaseModel):
    name: str
    type: str
    description: str


class FailureMode(BaseModel):
    condition: str
    behavior: str
    recoverable: bool = True


class SkillExample(BaseModel):
    description: str
    invocation: str
    expected_output: str | None = None


class SkillDefinition(BaseModel):
    """The canonical schema for a Skill.md, parsed into structured form."""
    id: EntityID = Field(default_factory=lambda: EntityID(kind="skill"))
    name: str
    slug: str
    version: str = "1.0.0"
    category: SkillCategory
    purpose: str
    description: str
    inputs: list[SkillInput] = Field(default_factory=list)
    outputs: list[SkillOutput] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    failure_modes: list[FailureMode] = Field(default_factory=list)
    tool_dependencies: list[str] = Field(default_factory=list)
    determinism: DeterminismLevel = DeterminismLevel.GENERATIVE
    composable_with: list[str] = Field(default_factory=list)
    examples: list[SkillExample] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_slug(self) -> Self:
        if not self.slug.replace("-", "").replace("_", "").isalnum():
            msg = f"Slug must be alphanumeric with hyphens/underscores: {self.slug}"
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# Tool Schema
# ---------------------------------------------------------------------------

class ToolEndpoint(BaseModel):
    url: str
    method: str = "POST"
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = 30


class OAuthConfig(BaseModel):
    authorization_url: str
    token_url: str
    scopes: list[str] = Field(default_factory=list)
    client_id_env: str = ""
    client_secret_env: str = ""
    redirect_uri: str = "http://localhost:9876/callback"
    pkce: bool = True


class ToolDefinition(BaseModel):
    """Canonical schema for a registered tool."""
    id: EntityID = Field(default_factory=lambda: EntityID(kind="tool"))
    name: str
    slug: str
    version: str = "1.0.0"
    description: str
    auth_type: ToolAuthType = ToolAuthType.NONE
    oauth_config: OAuthConfig | None = None
    endpoints: list[ToolEndpoint] = Field(default_factory=list)
    health: ToolHealth = ToolHealth.UNKNOWN
    capabilities: list[Capability] = Field(default_factory=list)
    rate_limit_rpm: int | None = None
    tags: list[str] = Field(default_factory=list)
    verified: bool = False


# ---------------------------------------------------------------------------
# Event System
# ---------------------------------------------------------------------------

class Event(BaseModel):
    """Immutable event record for the event bus."""
    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    kind: str
    source: str
    data: dict[str, Any] = Field(default_factory=dict)
    severity: Severity = Severity.INFO
    correlation_id: UUID | None = None

    @property
    def epoch_ms(self) -> int:
        return int(self.timestamp.timestamp() * 1000)


# ---------------------------------------------------------------------------
# Checkpoint / Replay
# ---------------------------------------------------------------------------

class Checkpoint(BaseModel):
    """Serializable snapshot for deterministic replay."""
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    sequence: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    state: dict[str, Any]
    events_since_last: list[Event] = Field(default_factory=list)
    checksum: str = ""

    def compute_checksum(self) -> str:
        raw = orjson_dumps(self.state) if self.state else b""
        return hashlib.sha256(raw).hexdigest()[:16]


def orjson_dumps(obj: Any) -> bytes:
    import orjson
    return orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)


# ---------------------------------------------------------------------------
# Artifact
# ---------------------------------------------------------------------------

class Artifact(BaseModel):
    """Any exportable output the system produces."""
    id: EntityID = Field(default_factory=lambda: EntityID(kind="artifact"))
    name: str
    format: ArtifactFormat
    content: str | bytes = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_session: UUID | None = None
    exportable: bool = True


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class Session(BaseModel):
    """Top-level session tracking."""
    id: UUID = Field(default_factory=uuid4)
    state: SessionState = SessionState.INITIALIZING
    agent_manifest: CapabilityManifest | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    checkpoints: list[UUID] = Field(default_factory=list)
    artifacts: list[UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def touch(self) -> None:
        self.last_activity = datetime.now(timezone.utc)
