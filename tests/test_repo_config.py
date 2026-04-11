"""Tests for repository configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agent_loop.core.repo_config import (
    CompatLoopExecution,
    DelegatedExecution,
    WorkflowProvider,
    get_effective_provider,
    get_repo_config_path,
    load_compat_loop_repo_config,
    load_repo_config,
)


def test_fails_when_repo_config_is_absent(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Missing agent-loop repo config"):
        load_repo_config(str(tmp_path))


def test_loads_compat_loop_config(tmp_path: Path) -> None:
    config_dir = Path(os.path.dirname(get_repo_config_path(str(tmp_path))))
    config_dir.mkdir(parents=True)

    Path(get_repo_config_path(str(tmp_path))).write_text(
        json.dumps(
            {
                "configVersion": 1,
                "plansDir": "plans",
                "reviewsDir": "reviews",
                "runDir": ".agent-loop/runs",
                "maxAttempts": 4,
                "prompts": {
                    "implementer": ".agent-loop/prompts/implementer.md",
                    "reviewer": ".agent-loop/prompts/code-reviewer.md",
                },
                "checksFile": ".agent-loop/checks.json",
                "execution": {
                    "mode": "compat-loop",
                    "defaultProvider": "codex",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    config = load_repo_config(str(tmp_path))
    assert config.configVersion == 1
    assert config.plansDir == "plans"
    assert config.reviewsDir == "reviews"
    assert config.execution.mode == "compat-loop"
    assert config.execution.defaultProvider.value == "codex"


def test_accepts_claude_as_compat_loop_provider(tmp_path: Path) -> None:
    config_dir = Path(os.path.dirname(get_repo_config_path(str(tmp_path))))
    config_dir.mkdir(parents=True)

    Path(get_repo_config_path(str(tmp_path))).write_text(
        json.dumps(
            {
                "configVersion": 1,
                "plansDir": "plans",
                "reviewsDir": "reviews",
                "runDir": ".agent-loop/runs",
                "maxAttempts": 4,
                "prompts": {
                    "implementer": ".agent-loop/prompts/implementer.md",
                    "reviewer": ".agent-loop/prompts/code-reviewer.md",
                },
                "checksFile": ".agent-loop/checks.json",
                "execution": {
                    "mode": "compat-loop",
                    "defaultProvider": "claude",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    config = load_repo_config(str(tmp_path))
    assert config.execution.mode == "compat-loop"
    assert config.execution.defaultProvider.value == "claude"


def test_loads_delegated_config(tmp_path: Path) -> None:
    config_dir = Path(os.path.dirname(get_repo_config_path(str(tmp_path))))
    config_dir.mkdir(parents=True)

    Path(get_repo_config_path(str(tmp_path))).write_text(
        json.dumps(
            {
                "configVersion": 1,
                "plansDir": "plans",
                "reviewsDir": "reviews",
                "execution": {
                    "mode": "delegated",
                    "provider": "codex",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    config = load_repo_config(str(tmp_path))
    assert config.configVersion == 1
    assert config.plansDir == "plans"
    assert config.reviewsDir == "reviews"
    assert config.execution.mode == "delegated"
    assert config.execution.provider.value == "codex"


def test_fails_when_compat_loop_loader_sees_delegated(tmp_path: Path) -> None:
    config_dir = Path(os.path.dirname(get_repo_config_path(str(tmp_path))))
    config_dir.mkdir(parents=True)

    Path(get_repo_config_path(str(tmp_path))).write_text(
        json.dumps(
            {
                "configVersion": 1,
                "plansDir": "plans",
                "reviewsDir": "reviews",
                "execution": {
                    "mode": "delegated",
                    "provider": "codex",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Expected compat-loop execution mode"):
        load_compat_loop_repo_config(str(tmp_path))


def test_loads_compat_loop_with_default_provider(tmp_path: Path) -> None:
    config_dir = Path(os.path.dirname(get_repo_config_path(str(tmp_path))))
    config_dir.mkdir(parents=True)

    Path(get_repo_config_path(str(tmp_path))).write_text(
        json.dumps(
            {
                "configVersion": 1,
                "plansDir": "plans",
                "reviewsDir": "reviews",
                "runDir": ".agent-loop/runs",
                "maxAttempts": 4,
                "prompts": {
                    "implementer": ".agent-loop/prompts/implementer.md",
                    "reviewer": ".agent-loop/prompts/code-reviewer.md",
                },
                "checksFile": ".agent-loop/checks.json",
                "execution": {
                    "mode": "compat-loop",
                    "defaultProvider": "codex",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    config = load_repo_config(str(tmp_path))
    assert config.execution.mode == "compat-loop"
    assert config.execution.defaultProvider.value == "codex"


def test_fails_when_repo_config_is_invalid(tmp_path: Path) -> None:
    config_dir = Path(os.path.dirname(get_repo_config_path(str(tmp_path))))
    config_dir.mkdir(parents=True)

    Path(get_repo_config_path(str(tmp_path))).write_text(
        json.dumps(
            {
                "configVersion": 2,
                "plansDir": "plans",
                "reviewsDir": "reviews",
                "execution": {
                    "mode": "delegated",
                    "provider": "codex",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid agent-loop repo config"):
        load_repo_config(str(tmp_path))


# --- getEffectiveProvider ---


def test_returns_default_provider_for_compat_loop() -> None:
    execution = CompatLoopExecution(mode="compat-loop", defaultProvider=WorkflowProvider.CLAUDE)
    result = get_effective_provider(execution)
    assert result == WorkflowProvider.CLAUDE


def test_returns_provider_for_delegated() -> None:
    execution = DelegatedExecution(mode="delegated", provider=WorkflowProvider.GEMINI)
    result = get_effective_provider(execution)
    assert result == WorkflowProvider.GEMINI
