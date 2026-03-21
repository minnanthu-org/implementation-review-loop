"""agent-loop loop — run-loop CLI subcommands."""

from __future__ import annotations

import sys

import click

from agent_loop.cli.agent_commands import (
    default_implementer_command,
    default_reviewer_command,
)
from agent_loop.cli.assets import resolve_asset_path
from agent_loop.core.providers import check_provider_available
from agent_loop.core.repo_config import WorkflowProvider
from agent_loop.core.run_loop import initialize_run, run_loop
from agent_loop.core.run_loop.state import AttemptTiming, RunLoopOptions
from agent_loop.core.run_loop.summary import format_duration


def _print_timing_table(timing: list[AttemptTiming]) -> None:
    """Print a timing summary table to stderr."""
    if not timing:
        return

    rows: list[tuple[str, str, str, str, str]] = []
    for t in timing:
        impl = format_duration(t["implement"])
        chk = format_duration(t["check"])
        rev = format_duration(t["review"])
        parts = [v for v in (t["implement"], t["check"], t["review"]) if v is not None]
        total = format_duration(sum(parts)) if parts else "-"
        rows.append((str(t["attempt"]), impl, chk, rev, total))

    all_impl = [t["implement"] for t in timing if t["implement"] is not None]
    all_chk = [t["check"] for t in timing if t["check"] is not None]
    all_rev = [t["review"] for t in timing if t["review"] is not None]
    total_impl = format_duration(sum(all_impl)) if all_impl else "-"
    total_chk = format_duration(sum(all_chk)) if all_chk else "-"
    total_rev = format_duration(sum(all_rev)) if all_rev else "-"
    all_vals = all_impl + all_chk + all_rev
    grand_total = format_duration(sum(all_vals)) if all_vals else "-"
    rows.append(("Total", total_impl, total_chk, total_rev, grand_total))

    headers = ("Attempt", "Implement", "Check", "Review", "Total")
    widths = [
        max(len(headers[i]), *(len(r[i]) for r in rows))
        for i in range(5)
    ]

    def sep(left: str, mid: str, right: str, fill: str = "─") -> str:
        return left + mid.join(fill * (w + 2) for w in widths) + right

    def row_str(vals: tuple[str, ...]) -> str:
        cells = " │ ".join(v.ljust(w) for v, w in zip(vals, widths))
        return f"│ {cells} │"

    lines = [
        sep("┌", "┬", "┐"),
        row_str(headers),
        sep("├", "┼", "┤"),
    ]
    for i, r in enumerate(rows):
        if i == len(rows) - 1:
            lines.append(sep("├", "┼", "┤"))
        lines.append(row_str(r))
    lines.append(sep("└", "┴", "┘"))

    sys.stderr.write("\n".join(lines) + "\n")


def _resolve_agent_commands(
    *,
    implementer_command: str | None,
    implementer_model: str | None = None,
    implementer_provider: WorkflowProvider | None,
    reviewer_command: str | None,
    reviewer_model: str | None = None,
    reviewer_provider: WorkflowProvider | None,
) -> tuple[str, str]:
    """Resolve implementer and reviewer commands from options."""
    # Pre-flight: verify provider CLIs are available before building commands.
    if not implementer_command and implementer_provider:
        check_provider_available(implementer_provider)
    if not reviewer_command and reviewer_provider:
        check_provider_available(reviewer_provider)

    effective_impl = implementer_command
    if not effective_impl and implementer_provider:
        effective_impl = default_implementer_command(
            implementer_provider, model=implementer_model
        )

    effective_rev = reviewer_command
    if not effective_rev and reviewer_provider:
        effective_rev = default_reviewer_command(
            reviewer_provider, model=reviewer_model
        )

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
    model_str: str | None = None,
    implementer_model_str: str | None = None,
    reviewer_model_str: str | None = None,
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

    impl_model = implementer_model_str or model_str
    rev_model = reviewer_model_str or model_str

    impl_cmd, rev_cmd = _resolve_agent_commands(
        implementer_command=implementer_command,
        implementer_model=impl_model,
        implementer_provider=impl_provider,
        reviewer_command=reviewer_command,
        reviewer_model=rev_model,
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
@click.option("--model", "model_str", default=None, help="Model for both roles.")
@click.option("--implementer-model", "implementer_model_str", default=None, help="Implementer model.")
@click.option("--reviewer-model", "reviewer_model_str", default=None, help="Reviewer model.")
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
    model_str: str | None,
    implementer_model_str: str | None,
    reviewer_model_str: str | None,
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
        model_str=model_str,
        implementer_model_str=implementer_model_str,
        reviewer_model_str=reviewer_model_str,
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
@click.option("--model", "model_str", default=None, help="Model for both roles.")
@click.option("--implementer-model", "implementer_model_str", default=None, help="Implementer model.")
@click.option("--reviewer-model", "reviewer_model_str", default=None, help="Reviewer model.")
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
    model_str: str | None,
    implementer_model_str: str | None,
    reviewer_model_str: str | None,
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
        model_str=model_str,
        implementer_model_str=implementer_model_str,
        reviewer_model_str=reviewer_model_str,
    )
    completed = run_loop(options)
    _print_timing_table(completed.timing)
    click.echo(
        f"[INFO] Completed stateless run at {completed.runDir} with status {completed.state.status.value}.",
        err=True,
    )
    sys.stdout.write(f"{completed.runDir}\n")
