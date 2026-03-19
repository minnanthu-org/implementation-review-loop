"""Default agent command generation."""

from __future__ import annotations

from agent_loop.core.repo_config import WorkflowProvider


def default_implementer_command(
    provider: WorkflowProvider = WorkflowProvider.CODEX,
    *,
    model: str | None = None,
) -> str:
    """Return the default implementer shell command for *provider*."""
    cmd = f"agent-loop agent run --provider {provider.value} --role implementer"
    if model:
        cmd += f" --model {model}"
    return cmd


def default_reviewer_command(
    provider: WorkflowProvider = WorkflowProvider.CODEX,
    *,
    model: str | None = None,
) -> str:
    """Return the default reviewer shell command for *provider*."""
    cmd = f"agent-loop agent run --provider {provider.value} --role reviewer"
    if model:
        cmd += f" --model {model}"
    return cmd
