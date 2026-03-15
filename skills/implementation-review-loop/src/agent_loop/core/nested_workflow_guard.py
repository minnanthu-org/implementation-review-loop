"""Nested workflow invocation guard."""

from __future__ import annotations

import os

ACTIVE_WORKFLOW_COMMAND_ENV = "WORKFLOW_ACTIVE_COMMAND"


def assert_no_nested_workflow_invocation(
    command_name: str,
    env: dict[str, str] | None = None,
) -> None:
    """Raise if a workflow command is already running in this process tree."""
    if env is None:
        env = dict(os.environ)

    active = env.get(ACTIVE_WORKFLOW_COMMAND_ENV)
    if not active:
        return

    raise RuntimeError(
        f"Nested workflow invocation is not allowed: "
        f"attempted {command_name} while {active} is already running."
    )


def build_workflow_command_environment(
    command_name: str,
    env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return a copy of *env* with ``WORKFLOW_ACTIVE_COMMAND`` set."""
    if env is None:
        env = dict(os.environ)
    return {**env, ACTIVE_WORKFLOW_COMMAND_ENV: command_name}
