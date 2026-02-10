---
name: Penetration Test Guide
slug: penetration-guide
version: 1.0.0
category: security
determinism: generative
tool_dependencies:
  (none)
composable_with: ["code-review", "code-generation", "code-refactor"]
tags: ["pentest", "checklist", "methodology"]
---

# Penetration Test Guide

## Purpose

Generate authorized penetration testing checklists and methodologies.

## Description

Penetration Test Guide is a canonical Super-MCP skill that provides structured, repeatable capability for generate authorized penetration testing checklists and methodologies. It integrates with the kernel's safety layer, event bus, and checkpoint system to ensure all operations are auditable and replayable.

## Inputs

- `request` (string) [required]: The primary input describing what needs to be done
- `context` (object): Additional context such as file paths, configurations, or constraints
- `options` (object): Skill-specific options to control behavior

## Outputs

- `result` (string): The primary output of the skill execution
- `artifacts` (array): Any generated artifacts (files, documents, configs)
- `metadata` (object): Execution metadata including timing, token usage, and decisions made

## Constraints

- Must pass safety layer evaluation before execution
- All outputs are logged to the event bus
- Determinism level: generative
- Must not exceed configured timeout (default: 300s)
- Must not produce outputs exceeding configured size limits

## Failure Modes

- Invalid input format → Return validation error with schema hints (recoverable)
- Tool dependency unavailable → Degrade gracefully or report missing tools (recoverable)
- Safety rule violation → Block execution and report violated rules (unrecoverable)
- Timeout exceeded → Return partial results with timeout indicator (recoverable)

## Examples

### Basic Usage

```
invoke penetration-guide --request "Describe what you need"
```

### With Context

```
invoke penetration-guide --request "Specific task" --context '{"path": "/src", "lang": "python"}'
```
