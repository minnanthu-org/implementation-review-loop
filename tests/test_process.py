"""Tests for shell command execution — ported from process.test.ts."""

import os

from agent_loop.core.process import run_shell_command


def test_captures_stdout_for_successful_command() -> None:
    result = run_shell_command(
        command="printf 'hello\\n'",
        cwd=os.getcwd(),
        timeout_ms=1_000,
    )

    assert result.exit_code == 0
    assert result.stdout == "hello\n"
    assert result.timed_out is False


def test_passes_stdin_text_to_command() -> None:
    result = run_shell_command(
        command="cat",
        cwd=os.getcwd(),
        stdin_text="from stdin\n",
        timeout_ms=1_000,
    )

    assert result.exit_code == 0
    assert result.stdout == "from stdin\n"
    assert result.timed_out is False


def test_times_out_long_running_command() -> None:
    result = run_shell_command(
        command="sleep 10",
        cwd=os.getcwd(),
        timeout_ms=50,
    )

    assert result.exit_code == 124
    assert result.timed_out is True
    assert "Command timed out after 50ms." in result.stderr
