"""Tests for agent_commands."""

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


class TestDefaultReviewerCommand:
    def test_targets_codex_by_default(self) -> None:
        cmd = default_reviewer_command()
        assert "codex" in cmd
        assert "--role reviewer" in cmd

    def test_targets_claude_when_requested(self) -> None:
        cmd = default_reviewer_command(WorkflowProvider.CLAUDE)
        assert "claude" in cmd
        assert "--role reviewer" in cmd
