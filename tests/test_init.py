"""Tests for init_cmd."""

import json
from pathlib import Path

from agent_loop.cli.init_cmd import initialize_repository
from agent_loop.core.repo_config import WorkflowProvider


class TestInitializeRepository:
    def test_creates_compat_loop_scaffolding(self, tmp_path: Path) -> None:
        result = initialize_repository(
            mode="compat-loop",
            provider=WorkflowProvider.CODEX,
            repo_path=str(tmp_path),
        )

        config = json.loads(
            (tmp_path / ".agent-loop" / "config.json").read_text(encoding="utf-8")
        )
        checks = json.loads(
            (tmp_path / ".agent-loop" / "checks.json").read_text(encoding="utf-8")
        )
        plan_template = (
            tmp_path / "docs" / "implementation-plans" / "TEMPLATE.md"
        ).read_text(encoding="utf-8")

        assert result.mode == "compat-loop"
        assert result.provider == WorkflowProvider.CODEX
        assert config["execution"]["mode"] == "compat-loop"
        assert config["execution"]["defaultProvider"] == "codex"
        assert checks["commands"] == []
        assert "# 実装計画書テンプレート" in plan_template
        assert len(result.created_files) > 0

    def test_creates_delegated_scaffolding_with_claude(self, tmp_path: Path) -> None:
        result = initialize_repository(
            mode="delegated",
            provider=WorkflowProvider.CLAUDE,
            repo_path=str(tmp_path),
        )

        config = json.loads(
            (tmp_path / ".agent-loop" / "config.json").read_text(encoding="utf-8")
        )

        assert result.mode == "delegated"
        assert result.provider == WorkflowProvider.CLAUDE
        assert config["execution"]["mode"] == "delegated"
        assert config["execution"]["provider"] == "claude"
        assert not any(f.endswith("checks.json") for f in result.created_files)

    def test_skips_files_that_already_exist(self, tmp_path: Path) -> None:
        initialize_repository(
            mode="compat-loop",
            provider=WorkflowProvider.CODEX,
            repo_path=str(tmp_path),
        )
        second = initialize_repository(
            mode="compat-loop",
            provider=WorkflowProvider.CODEX,
            repo_path=str(tmp_path),
        )

        assert len(second.created_files) == 0
        assert len(second.skipped_files) > 0
