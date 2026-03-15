"""agent-loop doctor — repository health check."""

from __future__ import annotations

import sys

import click

from agent_loop.core.doctor import run_doctor


@click.command("doctor")
@click.option(
    "--repo",
    default=".",
    type=click.Path(exists=False),
    help="Repository path.",
)
def doctor_command(repo: str) -> None:
    """Validate the agent-loop repository configuration."""
    result = run_doctor(repo)

    click.echo(f"[INFO] doctor ok: {result.repo_path}", err=True)
    click.echo(f"[INFO] mode: {result.mode}", err=True)

    for item in result.checked_items:
        click.echo(f"[INFO] checked: {item}", err=True)

    sys.stdout.write(f"{result.mode}\n")
