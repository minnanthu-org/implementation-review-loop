"""Repository health check."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from agent_loop.core.checks import load_checks_config
from agent_loop.core.providers import is_provider_available
from agent_loop.core.repo_config import (
    CompatLoopRepoConfig,
    RepoConfig,
    WorkflowProvider,
    load_repo_config,
)


@dataclass
class ProviderStatus:
    provider: str
    available: bool
    detail: str  # resolved path or CLI name


@dataclass
class DoctorResult:
    checked_items: list[str] = field(default_factory=list)
    mode: str = ""
    repo_path: str = ""
    providers: list[ProviderStatus] = field(default_factory=list)


def run_doctor(repo_path: str) -> DoctorResult:
    """Validate the repository configuration and required paths."""
    resolved_repo_path = str(Path(repo_path).resolve())
    repo_config = load_repo_config(resolved_repo_path)

    checked_items = [
        _assert_directory_exists(
            str(Path(resolved_repo_path) / repo_config.plansDir),
            f"plansDir ({repo_config.plansDir})",
        ),
        _assert_directory_exists(
            str(Path(resolved_repo_path) / repo_config.reviewsDir),
            f"reviewsDir ({repo_config.reviewsDir})",
        ),
    ]

    if repo_config.execution.mode == "compat-loop":
        compat_config = CompatLoopRepoConfig.model_validate(repo_config.model_dump())
        checked_items.extend(
            _validate_compat_loop_repo(resolved_repo_path, compat_config)
        )

    provider_statuses = _check_all_providers()

    return DoctorResult(
        checked_items=checked_items,
        mode=repo_config.execution.mode,
        repo_path=resolved_repo_path,
        providers=provider_statuses,
    )


def _validate_compat_loop_repo(
    repo_path: str, repo_config: CompatLoopRepoConfig
) -> list[str]:
    checks_config = load_checks_config(repo_path, repo_config.checksFile)

    return [
        _assert_directory_exists(
            str(Path(repo_path) / repo_config.runDir),
            f"runDir ({repo_config.runDir})",
        ),
        _assert_file_exists(
            str(Path(repo_path) / repo_config.prompts.implementer),
            f"prompts.implementer ({repo_config.prompts.implementer})",
        ),
        _assert_file_exists(
            str(Path(repo_path) / repo_config.prompts.reviewer),
            f"prompts.reviewer ({repo_config.prompts.reviewer})",
        ),
        f"checksFile ({repo_config.checksFile}): {len(checks_config.commands)} commands",
    ]


def _assert_directory_exists(target_path: str, label: str) -> str:
    p = Path(target_path)

    if not p.exists():
        raise FileNotFoundError(
            f"Missing required directory for {label}: {target_path}"
        )

    if not p.is_dir():
        raise NotADirectoryError(
            f"Expected directory for {label}: {target_path}"
        )

    return label


def _check_all_providers() -> list[ProviderStatus]:
    """Check availability of all known provider CLIs."""
    statuses: list[ProviderStatus] = []
    for provider in WorkflowProvider:
        available, detail = is_provider_available(provider)
        statuses.append(
            ProviderStatus(
                provider=provider.value,
                available=available,
                detail=detail,
            )
        )
    return statuses


def _assert_file_exists(target_path: str, label: str) -> str:
    p = Path(target_path)

    if not p.exists():
        raise FileNotFoundError(
            f"Missing required file for {label}: {target_path}"
        )

    if not p.is_file():
        raise IsADirectoryError(f"Expected file for {label}: {target_path}")

    return label
