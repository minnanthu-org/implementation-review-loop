"""Tests for repository health check."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_loop.core.doctor import run_doctor


def test_validates_compat_loop_repo(tmp_path: Path) -> None:
    # Create directories
    (tmp_path / "docs" / "implementation-plans").mkdir(parents=True)
    (tmp_path / "docs" / "plan-reviews").mkdir(parents=True)
    (tmp_path / ".loop" / "runs").mkdir(parents=True)
    (tmp_path / ".agent-loop" / "prompts").mkdir(parents=True)

    # Create config
    (tmp_path / ".agent-loop" / "config.json").write_text(
        json.dumps(
            {
                "configVersion": 1,
                "plansDir": "docs/implementation-plans",
                "reviewsDir": "docs/plan-reviews",
                "runDir": ".loop/runs",
                "maxAttempts": 3,
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

    # Create prompt files
    (tmp_path / ".agent-loop" / "prompts" / "implementer.md").write_text(
        "# Implementer\n", encoding="utf-8"
    )
    (tmp_path / ".agent-loop" / "prompts" / "code-reviewer.md").write_text(
        "# Code Reviewer\n", encoding="utf-8"
    )

    # Create checks file
    (tmp_path / ".agent-loop" / "checks.json").write_text(
        json.dumps({"commands": ["npm run build", "npm test"]}, indent=2),
        encoding="utf-8",
    )

    result = run_doctor(str(tmp_path))

    assert result.mode == "compat-loop"
    assert "plansDir (docs/implementation-plans)" in result.checked_items
    assert "reviewsDir (docs/plan-reviews)" in result.checked_items
    assert "runDir (.loop/runs)" in result.checked_items
    assert "checksFile (.agent-loop/checks.json): 2 commands" in result.checked_items


def test_validates_delegated_repo(tmp_path: Path) -> None:
    (tmp_path / "docs" / "implementation-plans").mkdir(parents=True)
    (tmp_path / "docs" / "plan-reviews").mkdir(parents=True)
    (tmp_path / ".agent-loop").mkdir(parents=True)

    (tmp_path / ".agent-loop" / "config.json").write_text(
        json.dumps(
            {
                "configVersion": 1,
                "plansDir": "docs/implementation-plans",
                "reviewsDir": "docs/plan-reviews",
                "execution": {
                    "mode": "delegated",
                    "provider": "codex",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = run_doctor(str(tmp_path))

    assert result.mode == "delegated"
    assert result.checked_items == [
        "plansDir (docs/implementation-plans)",
        "reviewsDir (docs/plan-reviews)",
    ]


def test_fails_when_checks_file_is_missing(tmp_path: Path) -> None:
    (tmp_path / "docs" / "implementation-plans").mkdir(parents=True)
    (tmp_path / "docs" / "plan-reviews").mkdir(parents=True)
    (tmp_path / ".loop" / "runs").mkdir(parents=True)
    (tmp_path / ".agent-loop" / "prompts").mkdir(parents=True)

    (tmp_path / ".agent-loop" / "config.json").write_text(
        json.dumps(
            {
                "configVersion": 1,
                "plansDir": "docs/implementation-plans",
                "reviewsDir": "docs/plan-reviews",
                "runDir": ".loop/runs",
                "maxAttempts": 3,
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

    (tmp_path / ".agent-loop" / "prompts" / "implementer.md").write_text(
        "# Implementer\n", encoding="utf-8"
    )
    (tmp_path / ".agent-loop" / "prompts" / "code-reviewer.md").write_text(
        "# Code Reviewer\n", encoding="utf-8"
    )

    with pytest.raises(FileNotFoundError, match="Missing checks file"):
        run_doctor(str(tmp_path))
