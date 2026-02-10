"""Skill loader — parses Skill.md files into SkillDefinition objects.

Each skill lives as a standalone Markdown file with structured frontmatter.
The loader validates, indexes, and registers skills with the kernel.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import structlog

from src.kernel.types import (
    DeterminismLevel,
    FailureMode,
    SkillCategory,
    SkillDefinition,
    SkillExample,
    SkillInput,
    SkillOutput,
)

logger = structlog.get_logger(__name__)


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Extract YAML-like frontmatter from Markdown."""
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
    if not match:
        return {}, content

    fm_text, body = match.group(1), match.group(2)
    frontmatter: dict[str, Any] = {}

    current_key = ""
    current_list: list[str] = []

    for line in fm_text.split("\n"):
        line = line.rstrip()
        if not line:
            continue

        if line.startswith("  - "):
            current_list.append(line.strip("  - ").strip())
            frontmatter[current_key] = current_list
        elif ": " in line:
            key, value = line.split(": ", 1)
            key = key.strip()
            value = value.strip()

            if value == "" or value == "[]":
                current_key = key
                current_list = []
                frontmatter[key] = current_list
            elif value.startswith("[") and value.endswith("]"):
                items = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
                frontmatter[key] = items
            elif value.lower() in ("true", "false"):
                frontmatter[key] = value.lower() == "true"
            else:
                frontmatter[key] = value
                current_key = key
                current_list = []

    return frontmatter, body


def _parse_section(body: str, header: str) -> str:
    """Extract content under a specific ## header."""
    pattern = rf"## {re.escape(header)}\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, body, re.DOTALL)
    return match.group(1).strip() if match else ""


def _parse_list_section(body: str, header: str) -> list[str]:
    """Extract a bullet list under a header."""
    content = _parse_section(body, header)
    if not content:
        return []
    return [line.lstrip("- ").strip() for line in content.split("\n") if line.strip().startswith("-")]


def _parse_inputs(body: str) -> list[SkillInput]:
    content = _parse_section(body, "Inputs")
    if not content:
        return []
    inputs = []
    for line in content.split("\n"):
        if not line.strip().startswith("-"):
            continue
        line = line.lstrip("- ").strip()
        match = re.match(r"`(\w+)`\s*\((\w+)\)\s*(?:\[required\])?\s*[:\-]?\s*(.*)", line)
        if match:
            name, type_, desc = match.groups()
            inputs.append(SkillInput(
                name=name,
                type=type_,
                description=desc.strip(),
                required="required" in line.lower(),
            ))
        else:
            match2 = re.match(r"`(\w+)`\s*[:\-]\s*(.*)", line)
            if match2:
                inputs.append(SkillInput(
                    name=match2.group(1),
                    type="string",
                    description=match2.group(2).strip(),
                ))
    return inputs


def _parse_outputs(body: str) -> list[SkillOutput]:
    content = _parse_section(body, "Outputs")
    if not content:
        return []
    outputs = []
    for line in content.split("\n"):
        if not line.strip().startswith("-"):
            continue
        line = line.lstrip("- ").strip()
        match = re.match(r"`(\w+)`\s*\((\w+)\)\s*[:\-]?\s*(.*)", line)
        if match:
            outputs.append(SkillOutput(
                name=match.group(1),
                type=match.group(2),
                description=match.group(3).strip(),
            ))
        else:
            match2 = re.match(r"`(\w+)`\s*[:\-]\s*(.*)", line)
            if match2:
                outputs.append(SkillOutput(
                    name=match2.group(1),
                    type="string",
                    description=match2.group(2).strip(),
                ))
    return outputs


def _parse_failure_modes(body: str) -> list[FailureMode]:
    content = _parse_section(body, "Failure Modes")
    if not content:
        return []
    modes = []
    for line in content.split("\n"):
        if not line.strip().startswith("-"):
            continue
        line = line.lstrip("- ").strip()
        parts = line.split("→")
        if len(parts) >= 2:
            condition = parts[0].strip()
            behavior = parts[1].strip()
            recoverable = "unrecoverable" not in behavior.lower()
            modes.append(FailureMode(
                condition=condition,
                behavior=behavior,
                recoverable=recoverable,
            ))
    return modes


def _parse_examples(body: str) -> list[SkillExample]:
    content = _parse_section(body, "Examples")
    if not content:
        return []
    examples = []
    blocks = re.split(r"\n###\s+", content)
    for block in blocks:
        if not block.strip():
            continue
        lines = block.strip().split("\n")
        desc = lines[0].strip() if lines else ""
        code_match = re.search(r"```.*?\n(.*?)```", block, re.DOTALL)
        invocation = code_match.group(1).strip() if code_match else ""
        if desc and invocation:
            examples.append(SkillExample(description=desc, invocation=invocation))
    return examples


def parse_skill_md(content: str) -> SkillDefinition:
    """Parse a Skill.md string into a SkillDefinition."""
    frontmatter, body = _parse_frontmatter(content)

    name = frontmatter.get("name", "Unknown")
    slug = frontmatter.get("slug", name.lower().replace(" ", "-"))
    category_str = frontmatter.get("category", "system")
    determinism_str = frontmatter.get("determinism", "generative")

    try:
        category = SkillCategory(category_str.lower())
    except ValueError:
        category = SkillCategory.SYSTEM

    try:
        determinism = DeterminismLevel(determinism_str.lower())
    except ValueError:
        determinism = DeterminismLevel.GENERATIVE

    return SkillDefinition(
        name=name,
        slug=slug,
        version=frontmatter.get("version", "1.0.0"),
        category=category,
        purpose=_parse_section(body, "Purpose") or frontmatter.get("purpose", ""),
        description=_parse_section(body, "Description") or frontmatter.get("description", ""),
        inputs=_parse_inputs(body),
        outputs=_parse_outputs(body),
        constraints=_parse_list_section(body, "Constraints"),
        failure_modes=_parse_failure_modes(body),
        tool_dependencies=frontmatter.get("tool_dependencies", []),
        determinism=determinism,
        composable_with=frontmatter.get("composable_with", []),
        examples=_parse_examples(body),
        tags=frontmatter.get("tags", []),
    )


async def load_skills_from_directory(skills_dir: Path) -> list[SkillDefinition]:
    """Load all Skill.md files from a directory."""
    skills = []
    if not skills_dir.exists():
        await logger.awarn("skills_dir_not_found", path=str(skills_dir))
        return skills

    for md_file in sorted(skills_dir.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
            skill = parse_skill_md(content)
            skills.append(skill)
        except Exception as e:
            await logger.aerror("skill_parse_failed", file=md_file.name, error=str(e))

    await logger.ainfo("skills_loaded", count=len(skills))
    return skills
