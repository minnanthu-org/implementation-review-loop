"""agent-loop init — repository scaffolding."""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import click

from agent_loop.cli.assets import resolve_asset_path
from agent_loop.core.repo_config import WorkflowProvider

ExecutionMode = Literal["compat-loop", "delegated"]


@dataclass
class InitResult:
    created_files: list[str] = field(default_factory=list)
    mode: ExecutionMode = "compat-loop"
    provider: WorkflowProvider = WorkflowProvider.CODEX
    repo_path: str = ""
    skipped_files: list[str] = field(default_factory=list)


def initialize_repository(
    *,
    mode: ExecutionMode,
    provider: WorkflowProvider,
    repo_path: str,
) -> InitResult:
    """Create the agent-loop scaffolding inside *repo_path*."""
    resolved = str(Path(repo_path).resolve())
    created_files: list[str] = []
    skipped_files: list[str] = []

    base_files = [
        {
            "source": resolve_asset_path("templates", "plans", "implementation-plan.md"),
            "destination": str(Path(resolved) / "docs" / "implementation-plans" / "TEMPLATE.md"),
        },
        {
            "source": resolve_asset_path("templates", "plans", "plan-review.md"),
            "destination": str(Path(resolved) / "docs" / "plan-reviews" / "TEMPLATE.md"),
        },
        {
            "source": resolve_asset_path("templates", "config", f"{mode}.json"),
            "destination": str(Path(resolved) / ".agent-loop" / "config.json"),
        },
    ]

    compat_files = [
        {
            "source": resolve_asset_path("templates", "config", "checks.json"),
            "destination": str(Path(resolved) / ".agent-loop" / "checks.json"),
        },
        {
            "source": resolve_asset_path("templates", "prompts", "implementer.md"),
            "destination": str(
                Path(resolved) / ".agent-loop" / "prompts" / "implementer.md"
            ),
        },
        {
            "source": resolve_asset_path("templates", "prompts", "code-reviewer.md"),
            "destination": str(
                Path(resolved) / ".agent-loop" / "prompts" / "code-reviewer.md"
            ),
        },
    ]

    files = [*base_files, *(compat_files if mode == "compat-loop" else [])]

    # Create required directories
    (Path(resolved) / ".agent-loop").mkdir(parents=True, exist_ok=True)
    (Path(resolved) / "docs" / "implementation-plans").mkdir(parents=True, exist_ok=True)
    (Path(resolved) / "docs" / "plan-reviews").mkdir(parents=True, exist_ok=True)
    if mode == "compat-loop":
        (Path(resolved) / ".agent-loop" / "prompts").mkdir(parents=True, exist_ok=True)
        (Path(resolved) / ".agent-loop" / "runs").mkdir(parents=True, exist_ok=True)

    for file_entry in files:
        dest = file_entry["destination"]
        if Path(dest).exists():
            skipped_files.append(dest)
            continue

        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_entry["source"], dest)

        if dest == str(Path(resolved) / ".agent-loop" / "config.json"):
            _write_config_provider(dest, mode, provider)

        created_files.append(dest)

    return InitResult(
        created_files=created_files,
        mode=mode,
        provider=provider,
        repo_path=resolved,
        skipped_files=skipped_files,
    )


def _write_config_provider(
    config_path: str,
    mode: ExecutionMode,
    provider: WorkflowProvider,
) -> None:
    """Patch the provider field in the config file."""
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if mode == "compat-loop":
        config["execution"]["defaultProvider"] = provider.value
        config["execution"].pop("provider", None)
    else:
        config["execution"]["provider"] = provider.value
    Path(config_path).write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )


@click.command("init")
@click.option(
    "--repo",
    default=".",
    type=click.Path(exists=False),
    help="Repository path.",
)
@click.option(
    "--mode",
    "mode",
    default="compat-loop",
    type=click.Choice(["compat-loop", "delegated"]),
    help="Execution mode.",
)
@click.option(
    "--provider",
    default="codex",
    type=click.Choice(["codex", "claude", "gemini"]),
    help="Default provider.",
)
def init_command(repo: str, mode: str, provider: str) -> None:
    """Initialize an agent-loop repository."""
    result = initialize_repository(
        mode=mode,  # type: ignore[arg-type]
        provider=WorkflowProvider(provider),
        repo_path=repo,
    )

    click.echo(f"[INFO] init ok: {result.repo_path}", err=True)
    click.echo(f"[INFO] mode: {result.mode}", err=True)
    click.echo(f"[INFO] provider: {result.provider.value}", err=True)

    for file_path in result.created_files:
        click.echo(f"[INFO] created: {file_path}", err=True)

    for file_path in result.skipped_files:
        click.echo(f"[INFO] skipped: {file_path}", err=True)

    sys.stdout.write(f"{result.repo_path}\n")
