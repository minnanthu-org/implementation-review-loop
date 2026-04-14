"""Shell command execution — sync subprocess wrapper."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class CommandExecutionResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool


def run_shell_command(
    *,
    command: str,
    cwd: str,
    env: dict[str, str] | None = None,
    stdin_text: str | None = None,
    timeout_ms: int | None = None,
) -> CommandExecutionResult:
    """Run a shell command via a login shell and capture output."""
    import shutil

    _shell = shutil.which("zsh") or shutil.which("bash") or "/bin/sh"

    timeout_s: float | None = None
    if timeout_ms is not None and timeout_ms > 0:
        timeout_s = timeout_ms / 1000.0

    try:
        proc = subprocess.run(
            [_shell, "-lc", command],
            cwd=cwd,
            env=env,
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return CommandExecutionResult(
            command=command,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            timed_out=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        stderr += f"Command timed out after {timeout_ms}ms.\n"
        return CommandExecutionResult(
            command=command,
            exit_code=124,
            stdout=stdout,
            stderr=stderr,
            timed_out=True,
        )


def ensure_successful_command(label: str, result: CommandExecutionResult) -> None:
    """Raise if command exited non-zero."""
    if result.exit_code == 0:
        return
    raise RuntimeError(
        f"{label} command failed with exit code {result.exit_code}: {result.command}\n"
        + (result.stderr or result.stdout)
    )


def shell_escape(value: str) -> str:
    """Single-quote escape a value for shell use."""
    return "'" + value.replace("'", "'\\''") + "'"
