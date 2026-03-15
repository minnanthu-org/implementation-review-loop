"""Tests for Claude CLI integration — ported from claude.test.ts."""

from __future__ import annotations

import json
from pathlib import Path

from agent_loop.core.providers.claude import build_structured_claude_command


def test_builds_structured_claude_command(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {
                    "verdict": {"type": "string"},
                },
                "required": ["verdict"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    command = build_structured_claude_command(
        cwd=str(tmp_path), schema_path=str(schema_path)
    )

    assert "claude -p" in command
    assert "--json-schema" in command
    assert "--permission-mode bypassPermissions" in command
    assert "--no-session-persistence" in command
