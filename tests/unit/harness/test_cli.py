from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from src.cli import _collect_prompt, cli

from .test_socket_server import HEAD, _chunk, _frame, _read_request, serve


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for var in (
        "SMCP_PROVIDERS_FILE",
        "SMCP_PROVIDER",
        "SMCP_MODEL",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "OLLAMA_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)


def test_providers_lists_presets_without_leaking_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-live-should-never-print")
    result = CliRunner().invoke(cli, ["providers", "--json"])
    assert result.exit_code == 0, result.output
    assert "sk-live-should-never-print" not in result.output
    data = json.loads(result.output)
    names = {p["name"]: p for p in data["providers"]}
    assert names["ollama"]["active"] is True
    assert names["openai"]["key"] == "set via OPENAI_API_KEY"
    assert names["anthropic"]["key"].startswith("MISSING")


def test_providers_reads_config_file(tmp_path: Path) -> None:
    cfg = tmp_path / "p.toml"
    cfg.write_text('default = "box"\n[providers.box]\npreset = "vllm"\nmodel = "m"\n')
    result = CliRunner().invoke(cli, ["-c", str(cfg), "providers"])
    assert result.exit_code == 0
    assert "* box" in result.output
    assert str(cfg) in result.output


def test_bad_config_exits_2(tmp_path: Path) -> None:
    cfg = tmp_path / "p.toml"
    cfg.write_text('[providers.x]\npreset="openai"\napi_key="sk"\n')
    result = CliRunner().invoke(cli, ["-c", str(cfg), "providers"])
    assert result.exit_code == 2
    assert "plaintext" in result.output


def test_start_requires_model() -> None:
    result = CliRunner().invoke(cli, ["-p", "ollama", "start", "--no-tui", "hi"])
    assert result.exit_code == 2
    assert "no model" in result.output


def test_start_missing_key_exits_3() -> None:
    result = CliRunner().invoke(cli, ["-p", "anthropic", "-m", "c", "start", "--no-tui", "hi"])
    assert result.exit_code == 3
    assert "ANTHROPIC_API_KEY" in result.output


def test_ping_unreachable_exits_4() -> None:
    result = CliRunner().invoke(cli, ["-e", "http://127.0.0.1:9/v1", "ping"])
    assert result.exit_code == 4


async def _one_shot_server_handler(reader, writer):  # type: ignore[no-untyped-def]
    await _read_request(reader)
    writer.write(HEAD)
    for frame in (
        _frame("four"),
        'data: {"choices":[],"usage":{"prompt_tokens":3,"completion_tokens":1}}\n\n',
        "data: [DONE]\n\n",
    ):
        _chunk(writer, frame)
    writer.write(b"0\r\n\r\n")
    await writer.drain()
    writer.close()


async def test_start_plain_streams_to_stdout() -> None:
    import asyncio

    async with serve(_one_shot_server_handler) as url:
        result = await asyncio.to_thread(
            CliRunner().invoke,
            cli,
            [
                "-p",
                "openai-compatible",
                "-e",
                url,
                "-m",
                "m",
                "start",
                "--no-tui",
                "--show-usage",
                "2+2?",
            ],
        )
    assert result.exit_code == 0, result.output
    assert result.stdout == "four\n"
    assert "[usage] in=3 out=1 total=4" in result.stderr


def test_collect_prompt_reads_pipe_and_ignores_non_pipe(tmp_path: Path) -> None:
    r, w = os.pipe()
    os.write(w, b"piped text")
    os.close(w)
    with os.fdopen(r) as stdin:
        assert _collect_prompt("summarise", stdin) == "summarise\n\npiped text"
    with Path(os.devnull).open() as devnull:  # character device: not treated as input
        assert _collect_prompt("only arg", devnull) == "only arg"
    f = tmp_path / "in.txt"
    f.write_text("from file")
    with f.open() as stdin:
        assert _collect_prompt(None, stdin) == "from file"
