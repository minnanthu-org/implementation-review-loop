"""Codex CLI integration."""

from __future__ import annotations

import os

from agent_loop.core.process import CommandExecutionResult, run_shell_command, shell_escape

DEFAULT_CODEX_EXEC_TIMEOUT_MS = 420_000


def build_structured_codex_command(
    *, cwd: str, model: str | None = None, output_path: str, schema_path: str
) -> str:
    """Build a Codex exec command with structured output."""
    escaped_schema_path = shell_escape(schema_path)
    escaped_output_path = shell_escape(output_path)
    escaped_repo_path = shell_escape(cwd)

    model_flag = f"-m {shell_escape(model)} " if model else ""

    return (
        f"codex exec --ephemeral --skip-git-repo-check --full-auto --color never "
        f"{model_flag}"
        f"-C {escaped_repo_path} --output-schema {escaped_schema_path} "
        f"-o {escaped_output_path} -"
    )


def run_structured_codex_prompt(
    *,
    command: str | None = None,
    cwd: str,
    env: dict[str, str] | None = None,
    model: str | None = None,
    output_path: str,
    prompt: str,
    schema_path: str,
    timeout_ms: int | None = None,
) -> CommandExecutionResult:
    """Run a structured Codex prompt."""
    resolved_command = command or build_structured_codex_command(
        cwd=cwd, model=model, output_path=output_path, schema_path=schema_path
    )
    merged_env = {**os.environ, **(env or {})}

    return run_shell_command(
        command=resolved_command,
        cwd=cwd,
        env=merged_env,
        stdin_text=prompt,
        timeout_ms=timeout_ms if timeout_ms is not None else DEFAULT_CODEX_EXEC_TIMEOUT_MS,
    )


