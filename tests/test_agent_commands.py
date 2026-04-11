"""Tests for agent_commands."""

import shlex

from agent_loop.cli.agent_commands import (
    default_implementer_command,
    default_reviewer_command,
)
from agent_loop.core.repo_config import WorkflowProvider


class TestDefaultImplementerCommand:
    def test_targets_codex_by_default(self) -> None:
        cmd = default_implementer_command()
        assert "codex" in cmd
        assert "--role implementer" in cmd

    def test_targets_claude_when_requested(self) -> None:
        cmd = default_implementer_command(WorkflowProvider.CLAUDE)
        assert "claude" in cmd
        assert "--role implementer" in cmd

    def test_simple_model_is_shell_quoted(self) -> None:
        cmd = default_implementer_command(model="sonnet")
        tokens = shlex.split(cmd)
        assert tokens[-2:] == ["--model", "sonnet"]

    def test_model_with_shell_metacharacters_is_escaped(self) -> None:
        """The whole malicious model string must survive as ONE shell token."""
        payload = "x; echo injected"
        cmd = default_implementer_command(model=payload)
        tokens = shlex.split(cmd)
        assert tokens[-2:] == ["--model", payload]

    def test_model_with_single_quote_is_escaped(self) -> None:
        payload = "a'b"
        cmd = default_implementer_command(model=payload)
        tokens = shlex.split(cmd)
        assert tokens[-2:] == ["--model", payload]


class TestDefaultReviewerCommand:
    def test_targets_codex_by_default(self) -> None:
        cmd = default_reviewer_command()
        assert "codex" in cmd
        assert "--role reviewer" in cmd

    def test_targets_claude_when_requested(self) -> None:
        cmd = default_reviewer_command(WorkflowProvider.CLAUDE)
        assert "claude" in cmd
        assert "--role reviewer" in cmd

    def test_model_with_shell_metacharacters_is_escaped(self) -> None:
        payload = "x; echo injected"
        cmd = default_reviewer_command(model=payload)
        tokens = shlex.split(cmd)
        assert tokens[-2:] == ["--model", payload]
