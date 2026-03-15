"""Shell command execution — sync subprocess wrapper matching process.ts."""

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
    """Run a shell command via ``/bin/zsh -lc`` and capture output.

    Mirrors the behaviour of ``runShellCommand`` in ``process.ts``.
    """
    timeout_s: float | None = None
    if timeout_ms is not None and timeout_ms > 0:
        timeout_s = timeout_ms / 1000.0

    timed_out = False
    try:
        proc = subprocess.run(
            ["/bin/zsh", "-lc", command],
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
        timed_out = True
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
            timed_out=timed_out,
        )
