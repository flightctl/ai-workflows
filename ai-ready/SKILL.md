---
name: ai-ready
description: Scans a codebase structure, audits AI convention files, and creates or updates AGENTS.md with project-specific build commands, test patterns, and coding standards. Use when onboarding a project for AI agents, setting up AI instructions, after significant codebase changes, or to audit AI convention files like AGENTS.md or .cursorrules.
---
# AI-Ready Workflow

Ensure a project is AI-ready by maintaining accurate AGENTS.md files.

## Usage

Run `/update` to execute the full workflow. See `skills/update.md` for detailed steps.

## Commands

Commands are in `commands/`.

- `/update` → `commands/update.md` — Scan codebase, audit AI convention files, create or update AGENTS.md. Accepts optional arguments for targeted updates (e.g., a subdirectory or focus area).
