"""agent-loop loop — run-loop CLI subcommands, matching run-loop.ts CLI."""

from __future__ import annotations

import sys

import click

from agent_loop.cli.agent_commands import (
    default_implementer_command,
    default_reviewer_command,
)
from agent_loop.cli.assets import resolve_asset_path
from agent_loop.core.repo_config import WorkflowProvider
from agent_loop.core.run_loop import initialize_run, run_loop
from agent_loop.core.run_loop.state import RunLoopOptions


def _resolve_agent_commands(
    *,
    implementer_command: str | None,
    implementer_provider: WorkflowProvider | None,
    reviewer_command: str | None,
    reviewer_provider: WorkflowProvider | None,
) -> tuple[str, str]:
    """Resolve implementer and reviewer commands from options."""
    effective_impl = implementer_command
    if not effective_impl and implementer_provider:
        effective_impl = default_implementer_command(implementer_provider)

    effective_rev = reviewer_command
    if not effective_rev and reviewer_provider:
        effective_rev = default_reviewer_command(reviewer_provider)

    if not effective_impl:
        raise click.UsageError(
            "--implementer-provider is required (or use --provider to set both, "
            "or use --implementer-command)"
        )

    if not effective_rev:
        raise click.UsageError(
            "--reviewer-provider is required (or use --provider to set both, "
            "or use --reviewer-command)"
        )

    return effective_impl, effective_rev


def _build_options(
    *,
    plan_path: str,
    repo: str,
    runs_dir: str | None,
    max_attempts: int | None,
    checks_file: str | None,
    check_commands: tuple[str, ...],
    implementer_command: str | None,
    reviewer_command: str | None,
    provider_str: str | None,
    implementer_provider_str: str | None,
    reviewer_provider_str: str | None,
) -> RunLoopOptions:
    """Build RunLoopOptions from Click params."""
    provider = WorkflowProvider(provider_str) if provider_str else None
    impl_provider = (
        WorkflowProvider(implementer_provider_str)
        if implementer_provider_str
        else provider
    )
    rev_provider = (
        WorkflowProvider(reviewer_provider_str)
        if reviewer_provider_str
        else provider
    )

    impl_cmd, rev_cmd = _resolve_agent_commands(
        implementer_command=implementer_command,
        implementer_provider=impl_provider,
        reviewer_command=reviewer_command,
        reviewer_provider=rev_provider,
    )

    return RunLoopOptions(
        checkCommands=list(check_commands),
        checksFile=checks_file,
        codeReviewSchemaPath=resolve_asset_path(
            "schemas", "code-review-output.schema.json"
        ),
        implementerCommand=impl_cmd,
        implementerSchemaPath=resolve_asset_path(
            "schemas", "implementer-output.schema.json"
        ),
        maxAttempts=max_attempts,
        planPath=plan_path,
        repoPath=repo,
        reviewerCommand=rev_cmd,
        runsDir=runs_dir,
    )


@click.command("init")
@click.option("--plan", "plan_path", required=True, help="Path to the plan file.")
@click.option("--repo", default=".", type=click.Path(exists=False), help="Repository path.")
@click.option("--runs-dir", default=None, help="Custom runs directory.")
@click.option("--max-attempts", default=None, type=int, help="Maximum number of attempts.")
@click.option("--checks-file", default=None, help="Path to checks config file.")
@click.option("--check-command", "check_commands", multiple=True, help="Check command(s).")
@click.option("--implementer-command", default=None, help="Custom implementer command.")
@click.option("--reviewer-command", default=None, help="Custom reviewer command.")
@click.option("--provider", "provider_str", default=None, type=click.Choice(["codex", "claude", "gemini"]), help="Provider for both roles.")
@click.option("--implementer-provider", "implementer_provider_str", default=None, type=click.Choice(["codex", "claude", "gemini"]), help="Implementer provider.")
@click.option("--reviewer-provider", "reviewer_provider_str", default=None, type=click.Choice(["codex", "claude", "gemini"]), help="Reviewer provider.")
def loop_init_command(
    plan_path: str,
    repo: str,
    runs_dir: str | None,
    max_attempts: int | None,
    checks_file: str | None,
    check_commands: tuple[str, ...],
    implementer_command: str | None,
    reviewer_command: str | None,
    provider_str: str | None,
    implementer_provider_str: str | None,
    reviewer_provider_str: str | None,
) -> None:
    """Initialize a run directory without executing the loop."""
    options = _build_options(
        plan_path=plan_path,
        repo=repo,
        runs_dir=runs_dir,
        max_attempts=max_attempts,
        checks_file=checks_file,
        check_commands=check_commands,
        implementer_command=implementer_command,
        reviewer_command=reviewer_command,
        provider_str=provider_str,
        implementer_provider_str=implementer_provider_str,
        reviewer_provider_str=reviewer_provider_str,
    )
    initialized = initialize_run(options)
    click.echo(
        f"[INFO] Initialized stateless run at {initialized.runDir}", err=True
    )
    sys.stdout.write(f"{initialized.runDir}\n")


@click.command("run")
@click.option("--plan", "plan_path", required=True, help="Path to the plan file.")
@click.option("--repo", default=".", type=click.Path(exists=False), help="Repository path.")
@click.option("--runs-dir", default=None, help="Custom runs directory.")
@click.option("--max-attempts", default=None, type=int, help="Maximum number of attempts.")
@click.option("--checks-file", default=None, help="Path to checks config file.")
@click.option("--check-command", "check_commands", multiple=True, help="Check command(s).")
@click.option("--implementer-command", default=None, help="Custom implementer command.")
@click.option("--reviewer-command", default=None, help="Custom reviewer command.")
@click.option("--provider", "provider_str", default=None, type=click.Choice(["codex", "claude", "gemini"]), help="Provider for both roles.")
@click.option("--implementer-provider", "implementer_provider_str", default=None, type=click.Choice(["codex", "claude", "gemini"]), help="Implementer provider.")
@click.option("--reviewer-provider", "reviewer_provider_str", default=None, type=click.Choice(["codex", "claude", "gemini"]), help="Reviewer provider.")
def loop_run_command(
    plan_path: str,
    repo: str,
    runs_dir: str | None,
    max_attempts: int | None,
    checks_file: str | None,
    check_commands: tuple[str, ...],
    implementer_command: str | None,
    reviewer_command: str | None,
    provider_str: str | None,
    implementer_provider_str: str | None,
    reviewer_provider_str: str | None,
) -> None:
    """Execute the implement-check-review loop."""
    options = _build_options(
        plan_path=plan_path,
        repo=repo,
        runs_dir=runs_dir,
        max_attempts=max_attempts,
        checks_file=checks_file,
        check_commands=check_commands,
        implementer_command=implementer_command,
        reviewer_command=reviewer_command,
        provider_str=provider_str,
        implementer_provider_str=implementer_provider_str,
        reviewer_provider_str=reviewer_provider_str,
    )
    completed = run_loop(options)
    click.echo(
        f"[INFO] Completed stateless run at {completed.runDir} with status {completed.state.status.value}.",
        err=True,
    )
    sys.stdout.write(f"{completed.runDir}\n")
