from __future__ import annotations

from pathlib import Path

import pytest

from src.harness.config import (
    PRESETS,
    HarnessConfig,
    Secret,
    key_status,
    resolve_api_key,
    resolve_profile,
)
from src.harness.errors import AuthenticationError, ConfigError

EMPTY = HarnessConfig(profiles={}, default=None, source=None)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "SMCP_PROVIDER",
        "OPENAI_API_KEY",
        "OPENAI_API_KEY_FILE",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_API_KEY_FILE",
        "OLLAMA_API_KEY",
        "OLLAMA_API_KEY_FILE",
    ):
        monkeypatch.delenv(var, raising=False)


def test_default_is_ollama_with_local_endpoint() -> None:
    p = resolve_profile(EMPTY)
    assert (p.name, p.kind, p.base_url) == ("ollama", "openai", "http://localhost:11434/v1")
    assert resolve_profile(EMPTY, "lmstudio").base_url == "http://localhost:1234/v1"
    assert resolve_profile(EMPTY, "generic_v1", endpoint="https://x.test/v1").name == (
        "openai-compatible"
    )


def test_local_provider_never_uses_another_providers_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
    for name in ("ollama", "lmstudio", "vllm"):
        assert resolve_api_key(resolve_profile(EMPTY, name)) is None
    assert resolve_api_key(resolve_profile(EMPTY, "openai")) == Secret("sk-openai")


def test_required_key_missing_raises_auth_error() -> None:
    with pytest.raises(AuthenticationError, match="ANTHROPIC_API_KEY"):
        resolve_api_key(PRESETS["anthropic"])


def test_key_file_precedence_and_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = tmp_path / "k"
    key.write_text("sk-from-file\n")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
    monkeypatch.setenv("OPENAI_API_KEY_FILE", str(key))
    assert resolve_api_key(PRESETS["openai"]) == Secret("sk-from-file")
    two = tmp_path / "two"
    two.write_text("a\nb\n")
    p = resolve_profile(EMPTY, "openai", api_key_file=two)
    with pytest.raises(ConfigError, match="exactly one"):
        resolve_api_key(p)
    with pytest.raises(ConfigError, match="cannot read"):
        resolve_api_key(resolve_profile(EMPTY, "openai", api_key_file=tmp_path / "missing"))


def test_api_key_env_override_replaces_profile_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-wrong")
    monkeypatch.setenv("GATEWAY_KEY", "sk-gw")
    p = resolve_profile(EMPTY, "openai", api_key_env="GATEWAY_KEY")
    assert resolve_api_key(p) == Secret("sk-gw")


def test_secret_never_renders() -> None:
    s = Secret("sk-very-secret")
    assert "sk-very" not in repr(s)
    assert "sk-very" not in str(s)
    assert "sk-very" not in f"{s}"
    assert s.reveal() == "sk-very-secret"


def test_config_file_profiles_and_default(tmp_path: Path) -> None:
    cfg = tmp_path / "providers.toml"
    cfg.write_text(
        """
default = "local"

[providers.local]
preset = "ollama"
model = "qwen2.5:0.5b"

[providers.gw]
kind = "openai"
base_url = "https://gw.example.com/v1"
api_key_env = "GW_KEY"
api_key_file = "gw.key"
headers = { "X-Org" = "lovelogic" }
read_timeout = 30
"""
    )
    config = HarnessConfig.load(cfg)
    p = resolve_profile(config)
    assert (p.name, p.model, p.base_url) == ("local", "qwen2.5:0.5b", "http://localhost:11434/v1")
    gw = resolve_profile(config, "gw", model="m")
    assert gw.api_key_file == tmp_path / "gw.key"
    assert dict(gw.headers) == {"X-Org": "lovelogic"}
    assert gw.read_timeout == 30
    assert not gw.requires_key


@pytest.mark.parametrize(
    ("body", "match"),
    [
        ('[providers.x]\npreset="openai"\napi_key="sk-1"\n', "plaintext"),
        ('[providers.x]\npreset="openai"\nheaders={Authorization="Bearer s"}\n', "credential"),
        ('[providers.x]\npreset="openai"\nbogus=1\n', "unknown keys"),
        ('[providers.x]\nmodel="m"\n', "needs 'preset' or 'kind'"),
        ('[providers.x]\npreset="nope"\n', "unknown preset"),
        ('default = "missing"\n', "neither defined"),
        ("extra = 1\n", "unknown top-level"),
        ("not toml [", "cannot read"),
    ],
)
def test_config_rejections(tmp_path: Path, body: str, match: str) -> None:
    cfg = tmp_path / "p.toml"
    cfg.write_text(body)
    with pytest.raises(ConfigError, match=match):
        HarnessConfig.load(cfg)


def test_missing_explicit_config_is_error_but_default_location_is_optional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ConfigError, match="not found"):
        HarnessConfig.load(tmp_path / "nope.toml")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("SMCP_PROVIDERS_FILE", raising=False)
    assert HarnessConfig.load().profiles == {}


@pytest.mark.parametrize(
    ("endpoint", "ok"),
    [
        ("http://localhost:8000/v1", True),
        ("http://127.0.0.1:1234/v1", True),
        ("http://[::1]:11434/v1", True),
        ("https://api.example.com/v1", True),
        ("http://10.0.0.5:8000/v1", False),
        ("http://example.com/v1", False),
        ("ftp://x/v1", False),
        ("https://user:pw@x.com/v1", False),
        ("localhost:11434", False),
    ],
)
def test_endpoint_validation(endpoint: str, ok: bool) -> None:
    if ok:
        resolve_profile(EMPTY, "openai-compatible", endpoint=endpoint)
    else:
        with pytest.raises(ConfigError):
            resolve_profile(EMPTY, "openai-compatible", endpoint=endpoint)


def test_unknown_provider_lists_known() -> None:
    with pytest.raises(ConfigError, match="known: .*anthropic"):
        resolve_profile(EMPTY, "nonexistent")


def test_key_status_never_contains_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-abc123")
    status = key_status(PRESETS["openai"])
    assert "sk-abc123" not in status
    assert "OPENAI_API_KEY" in status
    assert key_status(PRESETS["ollama"]) == "none (optional)"
    assert key_status(PRESETS["anthropic"]).startswith("MISSING")


def test_shipped_example_config_is_valid() -> None:
    example = Path(__file__).resolve().parents[3] / "providers.example.toml"
    config = HarnessConfig.load(example)
    assert config.default == "local"
    for name in config.profiles:
        resolve_profile(config, name)
