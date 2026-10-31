"""Provider profiles: built-in presets, TOML config file, CLI overrides, and keys.

Resolution order for every field: CLI flag > config-file profile > preset.

Keys are read only from the variables and files named by the *selected*
profile (``<api_key_env>`` / ``<api_key_env>_FILE`` / ``api_key_file``) or by
an explicit ``--api-key-env`` / ``--api-key-file`` flag. A local provider never
picks up ``OPENAI_API_KEY`` by accident, and plaintext keys are refused in the
config file.
"""

from __future__ import annotations

import ipaddress
import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from src.harness.errors import AuthenticationError, ConfigError

ProviderKind = Literal["openai", "anthropic"]

CONFIG_ENV_VAR = "SMCP_PROVIDERS_FILE"
DEFAULT_PROFILE_ENV_VAR = "SMCP_PROVIDER"


class Secret:
    """An API key that refuses to print itself."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "Secret('********')"

    __str__ = __repr__

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Secret) and other._value == self._value

    def __hash__(self) -> int:
        return hash(self._value)


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    """A fully resolved provider endpoint."""

    name: str
    kind: ProviderKind
    base_url: str
    model: str = ""
    api_key_env: str | None = None
    api_key_file: Path | None = None
    requires_key: bool = False
    stream_usage: bool = True
    max_tokens_field: str = "max_tokens"
    default_max_tokens: int | None = None
    headers: Mapping[str, str] = field(default_factory=dict)
    connect_timeout: float = 10.0
    read_timeout: float = 120.0
    max_retries: int = 3
    allow_insecure_http: bool = False
    anthropic_version: str = "2023-06-01"
    description: str = ""

    @property
    def api_key_file_env(self) -> str | None:
        return f"{self.api_key_env}_FILE" if self.api_key_env else None


PRESETS: dict[str, ProviderProfile] = {
    "ollama": ProviderProfile(
        name="ollama",
        kind="openai",
        base_url="http://localhost:11434/v1",
        api_key_env="OLLAMA_API_KEY",
        description="Ollama (OpenAI-compatible /v1)",
    ),
    "lmstudio": ProviderProfile(
        name="lmstudio",
        kind="openai",
        base_url="http://localhost:1234/v1",
        api_key_env="LMSTUDIO_API_KEY",
        description="LM Studio local server",
    ),
    "vllm": ProviderProfile(
        name="vllm",
        kind="openai",
        base_url="http://localhost:8000/v1",
        api_key_env="VLLM_API_KEY",
        description="vLLM OpenAI-compatible server",
    ),
    "openai": ProviderProfile(
        name="openai",
        kind="openai",
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        requires_key=True,
        max_tokens_field="max_completion_tokens",
        description="OpenAI API",
    ),
    "anthropic": ProviderProfile(
        name="anthropic",
        kind="anthropic",
        base_url="https://api.anthropic.com/v1",
        api_key_env="ANTHROPIC_API_KEY",
        requires_key=True,
        default_max_tokens=4096,
        description="Anthropic Messages API",
    ),
    "openai-compatible": ProviderProfile(
        name="openai-compatible",
        kind="openai",
        base_url="",
        api_key_env="SMCP_LLM_API_KEY",
        description="Any OpenAI-compatible base URL (set base_url / --endpoint)",
    ),
}

_ALIASES = {
    "generic": "openai-compatible",
    "generic_v1": "openai-compatible",
    "lm-studio": "lmstudio",
}

_PROFILE_KEYS = {
    "preset",
    "kind",
    "base_url",
    "model",
    "api_key_env",
    "api_key_file",
    "requires_key",
    "stream_usage",
    "max_tokens_field",
    "default_max_tokens",
    "headers",
    "connect_timeout",
    "read_timeout",
    "max_retries",
    "allow_insecure_http",
    "anthropic_version",
    "description",
}

_SECRET_HEADER_NAMES = {"authorization", "x-api-key", "api-key", "proxy-authorization"}


def default_config_path() -> Path:
    """``$SMCP_PROVIDERS_FILE`` or ``$XDG_CONFIG_HOME/super-mcp/providers.toml``."""
    explicit = os.environ.get(CONFIG_ENV_VAR)
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "super-mcp" / "providers.toml"


@dataclass(frozen=True, slots=True)
class HarnessConfig:
    """Parsed config file: named profiles plus the default profile name."""

    profiles: Mapping[str, ProviderProfile]
    default: str | None
    source: Path | None

    @classmethod
    def load(cls, path: Path | None = None, *, required: bool = False) -> HarnessConfig:
        """Load the TOML config. A missing default-location file is not an error."""
        cfg_path = path or default_config_path()
        if not cfg_path.exists():
            if required or path is not None:
                raise ConfigError(f"config file not found: {cfg_path}")
            return cls(profiles={}, default=None, source=None)
        try:
            raw = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigError(f"cannot read config {cfg_path}: {exc}") from exc
        return cls.from_mapping(raw, source=cfg_path)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], *, source: Path | None = None) -> HarnessConfig:
        unknown_top = set(raw) - {"default", "providers"}
        if unknown_top:
            raise ConfigError(f"unknown top-level config keys: {sorted(unknown_top)}")
        default = raw.get("default")
        if default is not None and not isinstance(default, str):
            raise ConfigError("'default' must be a profile name string")
        providers = raw.get("providers", {})
        if not isinstance(providers, Mapping):
            raise ConfigError("[providers] must be a table")
        profiles = {
            name: _profile_from_table(name, table, base_dir=source.parent if source else None)
            for name, table in providers.items()
        }
        if default is not None and default not in profiles and _canonical(default) not in PRESETS:
            raise ConfigError(f"default profile {default!r} is neither defined nor a preset")
        return cls(profiles=profiles, default=default, source=source)


def _canonical(name: str) -> str:
    lowered = name.strip().lower()
    return _ALIASES.get(lowered, lowered)


def _profile_from_table(name: str, table: object, *, base_dir: Path | None) -> ProviderProfile:
    if not isinstance(table, Mapping):
        raise ConfigError(f"[providers.{name}] must be a table")
    if "api_key" in table:
        raise ConfigError(
            f"[providers.{name}] contains a plaintext 'api_key'; use api_key_env or "
            "api_key_file instead"
        )
    unknown = set(table) - _PROFILE_KEYS
    if unknown:
        raise ConfigError(f"[providers.{name}] unknown keys: {sorted(unknown)}")

    preset_name = table.get("preset")
    if preset_name is not None:
        canonical = _canonical(str(preset_name))
        if canonical not in PRESETS:
            raise ConfigError(f"[providers.{name}] unknown preset {preset_name!r}")
        base = replace(PRESETS[canonical], name=name)
    elif "kind" in table:
        kind = table["kind"]
        if kind not in ("openai", "anthropic"):
            raise ConfigError(f"[providers.{name}] kind must be 'openai' or 'anthropic'")
        base = replace(
            PRESETS["anthropic" if kind == "anthropic" else "openai-compatible"],
            name=name,
            api_key_env=None,
            requires_key=False,
        )
    elif _canonical(name) in PRESETS:
        base = PRESETS[_canonical(name)]
    else:
        raise ConfigError(f"[providers.{name}] needs 'preset' or 'kind'")

    updates: dict[str, Any] = {}
    for key, value in table.items():
        if key in ("preset", "kind"):
            continue
        if key == "api_key_file":
            p = Path(str(value)).expanduser()
            if not p.is_absolute() and base_dir is not None:
                p = base_dir / p
            updates[key] = p
        elif key == "headers":
            updates[key] = _validate_headers(name, value)
        else:
            updates[key] = value
    try:
        return replace(base, **updates)
    except TypeError as exc:  # pragma: no cover - guarded by _PROFILE_KEYS
        raise ConfigError(f"[providers.{name}] {exc}") from exc


def _validate_headers(name: str, value: object) -> dict[str, str]:
    if not isinstance(value, Mapping) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    ):
        raise ConfigError(f"[providers.{name}] headers must be a table of strings")
    for key in value:
        if key.lower() in _SECRET_HEADER_NAMES:
            raise ConfigError(
                f"[providers.{name}] header {key!r} would hold a credential in plaintext; "
                "use api_key_env or api_key_file"
            )
    return dict(value)


def resolve_profile(
    config: HarnessConfig,
    provider: str | None = None,
    *,
    model: str | None = None,
    endpoint: str | None = None,
    api_key_env: str | None = None,
    api_key_file: Path | None = None,
) -> ProviderProfile:
    """Pick a profile and apply CLI overrides. Validates the result."""
    name = provider or os.environ.get(DEFAULT_PROFILE_ENV_VAR) or config.default or "ollama"
    if name in config.profiles:
        profile = config.profiles[name]
    elif _canonical(name) in config.profiles:
        profile = config.profiles[_canonical(name)]
    elif _canonical(name) in PRESETS:
        profile = PRESETS[_canonical(name)]
    else:
        known = sorted(set(config.profiles) | set(PRESETS))
        raise ConfigError(f"unknown provider {name!r}; known: {', '.join(known)}")

    updates: dict[str, Any] = {}
    if model:
        updates["model"] = model
    if endpoint:
        updates["base_url"] = endpoint
    if api_key_env:
        # An explicit variable replaces the profile's; its *_FILE twin is honoured too.
        updates["api_key_env"] = api_key_env
        updates["api_key_file"] = None
    if api_key_file:
        updates["api_key_file"] = api_key_file.expanduser()
    if updates:
        profile = replace(profile, **updates)
    validate_profile(profile)
    return profile


def validate_profile(profile: ProviderProfile) -> None:
    if not profile.base_url:
        raise ConfigError(
            f"provider {profile.name!r} has no base URL; pass --endpoint or set base_url"
        )
    parts = urlsplit(profile.base_url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ConfigError(f"invalid base URL {profile.base_url!r}: need http(s)://host[:port]/path")
    if parts.username or parts.password:
        raise ConfigError("credentials in the base URL are not allowed; use api_key_env")
    if (
        parts.scheme == "http"
        and not _is_loopback(parts.hostname)
        and not profile.allow_insecure_http
    ):
        raise ConfigError(
            f"refusing plain http to non-local host {parts.hostname!r}; use https or set "
            "allow_insecure_http = true for this profile"
        )
    if profile.read_timeout <= 0 or profile.connect_timeout <= 0:
        raise ConfigError("timeouts must be positive")
    if profile.max_retries < 0:
        raise ConfigError("max_retries must be >= 0")


def _is_loopback(host: str) -> bool:
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def resolve_api_key(
    profile: ProviderProfile, environ: Mapping[str, str] | None = None
) -> Secret | None:
    """Find the profile's key. Order: api_key_file, ``<ENV>_FILE``, ``<ENV>``.

    Raises :class:`AuthenticationError` when the profile requires a key and
    none is set, and :class:`ConfigError` for an unreadable or malformed file.
    """
    env = os.environ if environ is None else environ
    path: Path | None = profile.api_key_file
    source = "api_key_file"
    if path is None and profile.api_key_file_env and env.get(profile.api_key_file_env):
        path = Path(env[profile.api_key_file_env]).expanduser()
        source = profile.api_key_file_env
    if path is not None:
        return Secret(_read_key_file(path, source))
    if profile.api_key_env:
        value = env.get(profile.api_key_env, "").strip()
        if value:
            return Secret(value)
    if profile.requires_key:
        hint = (
            f"set {profile.api_key_env} or {profile.api_key_file_env}"
            if profile.api_key_env
            else "set api_key_env or api_key_file for this profile"
        )
        raise AuthenticationError(f"no API key configured ({hint})", provider=profile.name)
    return None


def _read_key_file(path: Path, source: str) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read key file from {source} ({path}): {exc.strerror}") from exc
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) != 1:
        raise ConfigError(
            f"key file from {source} ({path}) must contain exactly one non-empty line"
        )
    return lines[0].strip()


def key_status(profile: ProviderProfile, environ: Mapping[str, str] | None = None) -> str:
    """Human description of where the key would come from. Never includes the key."""
    env = os.environ if environ is None else environ
    if profile.api_key_file is not None:
        return (
            f"file ({profile.api_key_file})"
            if profile.api_key_file.exists()
            else (f"missing file ({profile.api_key_file})")
        )
    if profile.api_key_file_env and env.get(profile.api_key_file_env):
        return f"file via {profile.api_key_file_env}"
    if profile.api_key_env and env.get(profile.api_key_env, "").strip():
        return f"set via {profile.api_key_env}"
    if profile.requires_key:
        return f"MISSING (set {profile.api_key_env} or {profile.api_key_file_env})"
    return "none (optional)"


def all_profiles(config: HarnessConfig) -> dict[str, ProviderProfile]:
    """Presets overlaid with config-file profiles, in display order."""
    merged: dict[str, ProviderProfile] = dict(PRESETS)
    merged.update(config.profiles)
    return merged
