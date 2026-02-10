---
name: Onboarding Guide
slug: onboarding-guide
version: 1.0.0
category: communication
determinism: generative
tool_dependencies:
  - notion
composable_with: ["code-review", "code-generation", "code-refactor"]
tags: ["onboarding", "guide", "team"]
---

# Onboarding Guide

## Purpose

Create developer onboarding documentation for projects and teams.

## Description

Onboarding Guide is a canonical Super-MCP skill that provides structured, repeatable capability for create developer onboarding documentation for projects and teams. It integrates with the kernel's safety layer, event bus, and checkpoint system to ensure all operations are auditable and replayable.

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
invoke onboarding-guide --request "Describe what you need"
```

### With Context

```
invoke onboarding-guide --request "Specific task" --context '{"path": "/src", "lang": "python"}'
```
