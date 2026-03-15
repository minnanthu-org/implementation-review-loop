"""Repository configuration."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class WorkflowProvider(str, Enum):
    CODEX = "codex"
    CLAUDE = "claude"
    GEMINI = "gemini"


# --- Config schemas ---


class CompatLoopPrompts(BaseModel):
    implementer: Annotated[str, Field(min_length=1)]
    reviewer: Annotated[str, Field(min_length=1)]


class CompatLoopExecution(BaseModel):
    mode: Literal["compat-loop"]
    defaultProvider: WorkflowProvider


class DelegatedExecution(BaseModel):
    mode: Literal["delegated"]
    provider: WorkflowProvider


class CompatLoopRepoConfig(BaseModel):
    configVersion: Literal[1]
    plansDir: Annotated[str, Field(min_length=1)]
    reviewsDir: Annotated[str, Field(min_length=1)]
    runDir: Annotated[str, Field(min_length=1)]
    maxAttempts: Annotated[int, Field(ge=1)]
    prompts: CompatLoopPrompts
    checksFile: Annotated[str, Field(min_length=1)]
    execution: CompatLoopExecution


class DelegatedRepoConfig(BaseModel):
    configVersion: Literal[1]
    plansDir: Annotated[str, Field(min_length=1)]
    reviewsDir: Annotated[str, Field(min_length=1)]
    execution: DelegatedExecution


RepoConfig = Union[CompatLoopRepoConfig, DelegatedRepoConfig]


def get_effective_provider(
    execution: CompatLoopExecution | DelegatedExecution,
) -> WorkflowProvider:
    """Return the effective provider from the execution config."""
    if isinstance(execution, CompatLoopExecution):
        return execution.defaultProvider
    return execution.provider


def get_repo_config_path(repo_path: str) -> str:
    """Return the path to ``.agent-loop/config.json`` inside *repo_path*."""
    return str(Path(repo_path).resolve() / ".agent-loop" / "config.json")


def load_repo_config(repo_path: str) -> RepoConfig:
    """Load and validate the repo config from ``.agent-loop/config.json``."""
    config_path = get_repo_config_path(repo_path)

    try:
        contents = Path(config_path).read_text(encoding="utf-8")
        data = json.loads(contents)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Missing agent-loop repo config at {config_path}"
        ) from None
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid agent-loop repo config at {config_path}: {exc}"
        ) from None

    return _parse_repo_config(data, config_path)


def load_compat_loop_repo_config(repo_path: str) -> CompatLoopRepoConfig:
    """Load config and assert it uses ``compat-loop`` mode."""
    config = load_repo_config(repo_path)

    if config.execution.mode != "compat-loop":
        raise ValueError(
            f"Expected compat-loop execution mode in {get_repo_config_path(repo_path)}, "
            f"but found {config.execution.mode}"
        )

    return CompatLoopRepoConfig.model_validate(config.model_dump())


def _parse_repo_config(data: object, config_path: str) -> RepoConfig:
    """Try compat-loop first, then delegated.  Matches Zod's ``z.union``."""
    from pydantic import ValidationError

    errors: list[str] = []

    try:
        return CompatLoopRepoConfig.model_validate(data)
    except ValidationError as exc:
        errors.append(str(exc))

    try:
        return DelegatedRepoConfig.model_validate(data)
    except ValidationError as exc:
        errors.append(str(exc))

    raise ValueError(
        f"Invalid agent-loop repo config at {config_path}: {'; '.join(errors)}"
    )
