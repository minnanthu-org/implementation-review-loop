"""Check command configuration and execution."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ValidationError

from agent_loop.core.contracts import NonEmptyStr
from agent_loop.core.process import run_shell_command

DEFAULT_CHECK_COMMAND_TIMEOUT_MS = 120_000


@dataclass(frozen=True)
class CheckResult:
    command: str
    exit_code: int
    ok: bool
    stdout: str
    stderr: str


@dataclass(frozen=True)
class AttemptCheckResults:
    all_passed: bool
    attempt: int
    commands: list[CheckResult]


class ChecksConfig(BaseModel):
    commands: list[NonEmptyStr]


_REQUIRED_CHECKS_HEADING_RE = re.compile(
    r"^##(?:\s+\d+\.)?\s+(?:必須 checks|required checks)\s*$",
    re.IGNORECASE,
)
_REQUIRED_CHECKS_ITEM_RE = re.compile(r"^(?:[-*]|\d+\.)\s+`(.+?)`\s*$")


def get_checks_config_path(repo_path: str, checks_file: str) -> str:
    """Return the resolved path to the checks config file."""
    return str(Path(repo_path).resolve() / checks_file)


def load_checks_config(repo_path: str, checks_file: str) -> ChecksConfig:
    """Load and validate the checks config from *checks_file* relative to *repo_path*."""
    config_path = get_checks_config_path(repo_path, checks_file)

    try:
        contents = Path(config_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise FileNotFoundError(f"Missing checks file at {config_path}") from None

    try:
        data = json.loads(contents)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid checks file at {config_path}: {exc}"
        ) from None

    try:
        return ChecksConfig.model_validate(data)
    except ValidationError as exc:
        raise ValueError(
            f"Invalid checks file at {config_path}: {exc}"
        ) from None


def extract_plan_check_commands(plan_path: str) -> list[str]:
    """Extract check commands from the plan's required-checks section."""
    lines = Path(plan_path).read_text(encoding="utf-8").splitlines()
    in_required_checks = False
    commands: list[str] = []

    for line in lines:
        stripped = line.strip()

        if not in_required_checks:
            if _REQUIRED_CHECKS_HEADING_RE.match(stripped):
                in_required_checks = True
            continue

        if stripped.startswith("## "):
            break

        match = _REQUIRED_CHECKS_ITEM_RE.match(stripped)
        if match:
            commands.append(match.group(1).strip())

    return _deduplicate_commands(commands)


def resolve_configured_check_commands(
    *,
    check_commands: list[str],
    checks_file_path: str,
    plan_check_commands: list[str] | None = None,
) -> list[str]:
    """Merge repo, plan, and CLI check commands, deduplicating in declaration order."""
    contents = Path(checks_file_path).read_text(encoding="utf-8")
    data = json.loads(contents)
    config = ChecksConfig.model_validate(data)
    return _deduplicate_commands([
        *config.commands,
        *(plan_check_commands or []),
        *check_commands,
    ])


def run_checks(*, commands: list[str], cwd: str) -> list[CheckResult]:
    """Run each check command sequentially and collect results."""
    results: list[CheckResult] = []

    for command in commands:
        result = run_shell_command(
            command=command,
            cwd=cwd,
            env=dict(os.environ),
            timeout_ms=DEFAULT_CHECK_COMMAND_TIMEOUT_MS,
        )

        results.append(
            CheckResult(
                command=command,
                exit_code=result.exit_code,
                ok=result.exit_code == 0,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        )

    return results


def _deduplicate_commands(commands: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for command in commands:
        if command in seen:
            continue
        seen.add(command)
        result.append(command)

    return result
