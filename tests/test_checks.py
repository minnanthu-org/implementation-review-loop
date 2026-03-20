"""Tests for check command configuration and execution."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agent_loop.core.checks import (
    ChecksConfig,
    extract_plan_check_commands,
    load_checks_config,
    resolve_configured_check_commands,
    run_checks,
)


# --- load_checks_config ---


def test_loads_valid_checks_config(tmp_path: Path) -> None:
    checks_file = tmp_path / "checks.json"
    checks_file.write_text(
        json.dumps({"commands": ["npm run build", "npm test"]}),
        encoding="utf-8",
    )

    config = load_checks_config(str(tmp_path), "checks.json")
    assert config.commands == ["npm run build", "npm test"]


def test_fails_when_checks_file_is_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Missing checks file"):
        load_checks_config(str(tmp_path), "checks.json")


def test_fails_when_checks_file_has_invalid_json(tmp_path: Path) -> None:
    checks_file = tmp_path / "checks.json"
    checks_file.write_text("{invalid", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid checks file"):
        load_checks_config(str(tmp_path), "checks.json")


def test_fails_when_checks_file_has_invalid_schema(tmp_path: Path) -> None:
    checks_file = tmp_path / "checks.json"
    checks_file.write_text(json.dumps({"commands": [123]}), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid checks file"):
        load_checks_config(str(tmp_path), "checks.json")


def test_rejects_empty_command_string(tmp_path: Path) -> None:
    checks_file = tmp_path / "checks.json"
    checks_file.write_text(
        json.dumps({"commands": ["npm test", ""]}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="Invalid checks file"):
        load_checks_config(str(tmp_path), "checks.json")


# --- extract_plan_check_commands ---


def test_extracts_commands_from_required_checks_section(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(
        """# Plan

## 9. 必須 checks

- `python -m py_compile foo.py`
- `pytest -q`

## 10. 受け入れ条件

- ok
""",
        encoding="utf-8",
    )

    result = extract_plan_check_commands(str(plan))

    assert result == ["python -m py_compile foo.py", "pytest -q"]


def test_ignores_non_command_bullets_in_required_checks_section(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(
        """# Plan

## 9. 必須 checks

- ここには説明も書ける
- `pytest`

## 10. 受け入れ条件
""",
        encoding="utf-8",
    )

    result = extract_plan_check_commands(str(plan))

    assert result == ["pytest"]


# --- resolve_configured_check_commands ---


def test_merges_and_deduplicates_commands(tmp_path: Path) -> None:
    checks_file = tmp_path / "checks.json"
    checks_file.write_text(
        json.dumps({"commands": ["npm run build", "npm test"]}),
        encoding="utf-8",
    )

    result = resolve_configured_check_commands(
        check_commands=["npm test", "npm run lint"],
        checks_file_path=str(checks_file),
        plan_check_commands=["pytest -q", "npm test"],
    )

    assert result == ["npm run build", "npm test", "pytest -q", "npm run lint"]


# --- run_checks ---


def test_run_checks_collects_results(tmp_path: Path) -> None:
    results = run_checks(
        commands=["printf 'ok'", "exit 1"],
        cwd=str(tmp_path),
    )

    assert len(results) == 2
    assert results[0].ok is True
    assert results[0].exit_code == 0
    assert results[0].stdout == "ok"
    assert results[1].ok is False
    assert results[1].exit_code == 1


# --- ChecksConfig validation ---


def test_accepts_empty_commands_list() -> None:
    config = ChecksConfig.model_validate({"commands": []})
    assert config.commands == []
