"""CLI entry point — Click group and subcommand registration."""

from __future__ import annotations

import click

from agent_loop.cli.code_review_cmd import code_review_command
from agent_loop.cli.doctor_cmd import doctor_command
from agent_loop.cli.init_cmd import init_command
from agent_loop.cli.new_plan_cmd import new_plan_command
from agent_loop.cli.plan_review_cmd import plan_review_command
from agent_loop.cli.run_loop_cmd import loop_init_command, loop_run_command
from agent_loop.cli.workflow_agent import agent_run_command


@click.group()
def cli() -> None:
    """agent-loop — AI agent loop for structured code review and implementation workflows."""


# Top-level commands
cli.add_command(init_command)
cli.add_command(doctor_command)


# plan group
@cli.group("plan")
def plan_group() -> None:
    """Plan management commands."""


plan_group.add_command(new_plan_command)
plan_group.add_command(plan_review_command)


# code group
@cli.group("code")
def code_group() -> None:
    """Code review commands."""


code_group.add_command(code_review_command)


# loop group
@cli.group("loop")
def loop_group() -> None:
    """Run-loop commands."""


loop_group.add_command(loop_init_command)
loop_group.add_command(loop_run_command)


# agent group
@cli.group("agent")
def agent_group() -> None:
    """Workflow agent commands."""


agent_group.add_command(agent_run_command)


if __name__ == "__main__":
    cli()
