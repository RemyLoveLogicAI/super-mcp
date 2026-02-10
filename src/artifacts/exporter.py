"""Artifact Exporter — exports artifacts to multiple formats.

Supports Markdown, JSON, HTML, and plain text export of
kernel artifacts, session reports, and replay bundles.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from src.kernel.types import Artifact, ArtifactFormat

logger = structlog.get_logger(__name__)


class ArtifactExporter:
    """Export artifacts to files in various formats."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or Path.home() / ".super-mcp" / "artifacts"

    async def export(
        self,
        artifact: Artifact,
        filename: str | None = None,
        format_override: ArtifactFormat | None = None,
    ) -> Path:
        """Export a single artifact to disk."""
        self._output_dir.mkdir(parents=True, exist_ok=True)

        fmt = format_override or artifact.format
        ext_map = {
            ArtifactFormat.MARKDOWN: ".md",
            ArtifactFormat.JSON: ".json",
            ArtifactFormat.HTML: ".html",
            ArtifactFormat.TEXT: ".txt",
            ArtifactFormat.CODE: ".py",
            ArtifactFormat.BINARY: ".bin",
        }
        ext = ext_map.get(fmt, ".txt")

        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = artifact.name.replace(" ", "_").replace("/", "_")[:50]
            filename = f"{safe_name}_{ts}{ext}"

        path = self._output_dir / filename

        content = artifact.content
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(str(content), encoding="utf-8")

        await logger.ainfo("artifact_exported", path=str(path), format=fmt.value)
        return path

    async def export_session_report(
        self,
        session_data: dict[str, Any],
        filename: str | None = None,
    ) -> Path:
        """Export a session report as Markdown."""
        self._output_dir.mkdir(parents=True, exist_ok=True)

        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"session_report_{ts}.md"

        path = self._output_dir / filename

        lines = [
            f"# Super-MCP Session Report",
            f"",
            f"**Generated:** {datetime.now().isoformat()}",
            f"**Session ID:** {session_data.get('session_id', 'N/A')}",
            f"**State:** {session_data.get('session_state', 'N/A')}",
            f"",
            f"## Statistics",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Skills Registered | {session_data.get('skills_registered', 0)} |",
            f"| Tools Registered | {session_data.get('tools_registered', 0)} |",
            f"| Checkpoints | {session_data.get('checkpoints', 0)} |",
            f"| Artifacts | {session_data.get('artifacts', 0)} |",
            f"| Events Total | {session_data.get('events_total', 0)} |",
            f"",
        ]

        safety = session_data.get("safety_stats", {})
        if safety:
            lines.extend([
                f"## Safety",
                f"",
                f"| Metric | Value |",
                f"|--------|-------|",
            ])
            for key, val in safety.items():
                lines.append(f"| {key} | {val} |")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        await logger.ainfo("session_report_exported", path=str(path))
        return path

    async def export_json(self, data: Any, filename: str) -> Path:
        """Export arbitrary data as JSON."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        path = self._output_dir / filename
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        await logger.ainfo("json_exported", path=str(path))
        return path

    async def list_exports(self) -> list[dict[str, Any]]:
        """List all exported artifacts."""
        if not self._output_dir.exists():
            return []

        exports = []
        for p in sorted(self._output_dir.iterdir()):
            if p.is_file():
                exports.append({
                    "name": p.name,
                    "size_bytes": p.stat().st_size,
                    "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                    "path": str(p),
                })
        return exports
