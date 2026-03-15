"""Tests for Gemini CLI integration — ported from gemini.test.ts."""

from __future__ import annotations

from agent_loop.core.providers.gemini import build_structured_gemini_command


def test_builds_gemini_command_with_json_output_and_yolo() -> None:
    command = build_structured_gemini_command()

    assert "gemini" in command
    assert "--output-format json" in command
    assert "--yolo" in command
