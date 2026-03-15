"""Default agent command generation — matching agent-commands.ts."""

from __future__ import annotations

from agent_loop.core.repo_config import WorkflowProvider


def default_implementer_command(
    provider: WorkflowProvider = WorkflowProvider.CODEX,
) -> str:
    """Return the default implementer shell command for *provider*."""
    return f"agent-loop agent run --provider {provider.value} --role implementer"


def default_reviewer_command(
    provider: WorkflowProvider = WorkflowProvider.CODEX,
) -> str:
    """Return the default reviewer shell command for *provider*."""
    return f"agent-loop agent run --provider {provider.value} --role reviewer"
