"""Provider dispatcher."""

from __future__ import annotations

import os

from agent_loop.core.process import CommandExecutionResult, run_shell_command
from agent_loop.core.providers.claude import run_structured_claude_prompt
from agent_loop.core.providers.codex import run_structured_codex_prompt
from agent_loop.core.providers.gemini import run_structured_gemini_prompt
from agent_loop.core.repo_config import WorkflowProvider


def run_structured_prompt(
    *,
    command: str | None = None,
    cwd: str,
    env: dict[str, str] | None = None,
    model: str | None = None,
    output_path: str,
    prompt: str,
    provider: WorkflowProvider,
    schema_path: str,
    timeout_ms: int | None = None,
) -> CommandExecutionResult:
    """Dispatch a structured prompt to the appropriate provider CLI."""
    if command:
        merged_env = {**os.environ, **(env or {})}
        return run_shell_command(
            command=command,
            cwd=cwd,
            env=merged_env,
            stdin_text=prompt,
            timeout_ms=timeout_ms,
        )

    if provider == WorkflowProvider.CLAUDE:
        return run_structured_claude_prompt(
            cwd=cwd,
            env=env,
            model=model,
            output_path=output_path,
            prompt=prompt,
            schema_path=schema_path,
            timeout_ms=timeout_ms,
        )

    if provider == WorkflowProvider.GEMINI:
        return run_structured_gemini_prompt(
            cwd=cwd,
            env=env,
            model=model,
            output_path=output_path,
            prompt=prompt,
            schema_path=schema_path,
            timeout_ms=timeout_ms,
        )

    return run_structured_codex_prompt(
        cwd=cwd,
        env=env,
        model=model,
        output_path=output_path,
        prompt=prompt,
        schema_path=schema_path,
        timeout_ms=timeout_ms,
    )
