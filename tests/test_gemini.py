"""Tests for Gemini CLI integration — ported from gemini.test.ts."""

from __future__ import annotations

import shlex

from agent_loop.core.providers.gemini import build_structured_gemini_command


def test_builds_gemini_command_with_json_output_and_yolo() -> None:
    command = build_structured_gemini_command()

    assert "gemini" in command
    assert "--output-format json" in command
    assert "--yolo" in command


def test_gemini_command_escapes_model_with_shell_metacharacters() -> None:
    payload = "x; echo injected"
    command = build_structured_gemini_command(model=payload)
    tokens = shlex.split(command)
    assert tokens[-2:] == ["--model", payload]


def test_gemini_command_quotes_simple_model() -> None:
    command = build_structured_gemini_command(model="gemini-2.5-pro")
    tokens = shlex.split(command)
    assert tokens[-2:] == ["--model", "gemini-2.5-pro"]
