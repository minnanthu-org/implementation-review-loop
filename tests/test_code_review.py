"""Tests for code_review_cmd."""

import json
import os
import sys
import time
from pathlib import Path

import pytest

from agent_loop.cli.code_review_cmd import render_code_review_record, run_code_review
from agent_loop.core.checks import CheckResult
from agent_loop.core.contracts import (
    CodeReviewOutput,
    FindingSeverity,
    FindingStatus,
    ReviewFinding,
    ReviewVerdict,
)
from agent_loop.core.process import run_shell_command


def _write_compat_loop_config(
    repo_dir: Path,
    checks: list[str] | None = None,
) -> None:
    agent_loop_dir = repo_dir / ".agent-loop"
    prompt_dir = agent_loop_dir / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)

    (agent_loop_dir / "config.json").write_text(
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
    (agent_loop_dir / "checks.json").write_text(
        json.dumps({"commands": list(checks or [])}, indent=2),
        encoding="utf-8",
    )
    (prompt_dir / "implementer.md").write_text("# Implementer\n", encoding="utf-8")
    (prompt_dir / "code-reviewer.md").write_text("# Code Reviewer\n", encoding="utf-8")


def _expect_command_to_succeed(command: str, cwd: str) -> None:
    result = run_shell_command(
        command=command, cwd=cwd, env=dict(os.environ), timeout_ms=120_000
    )
    if result.exit_code != 0:
        raise RuntimeError(
            f"Command failed with exit code {result.exit_code}: {command}\n"
            + (result.stderr or result.stdout)
        )


def _build_reviewer_assertion_command(
    *,
    changed_files: list[str],
    checks_run: list[str],
    fixture_path: str,
) -> str:
    return (
        f"EXPECTED_CHANGED_FILES_JSON='{json.dumps(changed_files)}' "
        f"EXPECTED_CHECKS_JSON='{json.dumps(checks_run)}' "
        f"{sys.executable} {fixture_path}"
    )


class TestRenderCodeReviewRecord:
    def test_renders_code_review_record(self) -> None:
        review = render_code_review_record(
            check_results=[
                CheckResult(
                    command="npm test",
                    exit_code=0,
                    ok=True,
                    stdout="",
                    stderr="",
                ),
            ],
            output=CodeReviewOutput(
                verdict=ReviewVerdict.FIX,
                summaryMd="追加修正が必要です。",
                findings=[
                    ReviewFinding(
                        id="F-001",
                        severity=FindingSeverity.HIGH,
                        status=FindingStatus.OPEN,
                        summaryMd="null guard が不足しています。",
                        suggestedActionMd="null check を追加してください。",
                    ),
                ],
            ),
            plan_path="docs/implementation-plans/example.md",
            review_date="2026-03-14",
            title="Example",
        )

        assert "# Example 実装レビュー記録" in review
        assert "結論: `fix`" in review
        assert "### F-001" in review
        assert "## checks" in review


class TestRunCodeReview:
    def test_rejects_nested_workflow_invocation(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "docs" / "implementation-plans"
        plan_dir.mkdir(parents=True)
        _write_compat_loop_config(tmp_path)
        (plan_dir / "example.md").write_text(
            "# Example 実装計画書\n", encoding="utf-8"
        )

        original = os.environ.get("WORKFLOW_ACTIVE_COMMAND")
        os.environ["WORKFLOW_ACTIVE_COMMAND"] = "loop:run"

        try:
            with pytest.raises(RuntimeError, match="Nested workflow invocation is not allowed"):
                run_code_review(
                    check_commands=[],
                    plan_path="docs/implementation-plans/example.md",
                    repo_path=str(tmp_path),
                )
        finally:
            if original is None:
                os.environ.pop("WORKFLOW_ACTIVE_COMMAND", None)
            else:
                os.environ["WORKFLOW_ACTIVE_COMMAND"] = original

    def test_writes_implementation_review_record(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "docs" / "implementation-plans"
        fixture_dir = Path(__file__).parent / "fixtures"
        reviewer_fixture = str(fixture_dir / "mock_one_shot_code_reviewer.py")
        check_fixture = str(fixture_dir / "mock_check.py")

        plan_dir.mkdir(parents=True)
        _write_compat_loop_config(
            tmp_path, checks=[f"{sys.executable} {check_fixture}"]
        )
        (plan_dir / "example.md").write_text(
            "# Example 実装計画書\n\n## 3. 変更対象\n\n- `src/example.ts`\n",
            encoding="utf-8",
        )

        completed = run_code_review(
            check_commands=[],
            plan_path="docs/implementation-plans/example.md",
            repo_path=str(tmp_path),
            reviewer_command=f"{sys.executable} {reviewer_fixture}",
        )

        review = Path(completed.review_path).read_text(encoding="utf-8")

        assert completed.output.verdict == ReviewVerdict.APPROVE
        assert completed.review_path == str(
            tmp_path
            / "docs"
            / "implementation-reviews"
            / "example-implementation-review.md"
        )
        assert "# Example 実装レビュー記録" in review
        assert "結論: `approve`" in review
        assert f"- [成功] `{sys.executable}" in review

    def test_passes_actual_git_changed_files_to_reviewer(
        self, tmp_path: Path
    ) -> None:
        plan_dir = tmp_path / "docs" / "implementation-plans"
        source_dir = tmp_path / "src"
        fixture_dir = Path(__file__).parent / "fixtures"
        reviewer_fixture = str(fixture_dir / "mock_one_shot_code_reviewer_assert.py")
        check_fixture = str(fixture_dir / "mock_check.py")
        tracked_file = source_dir / "tracked.ts"
        untracked_file = source_dir / "untracked.ts"

        plan_dir.mkdir(parents=True)
        source_dir.mkdir(parents=True)
        _write_compat_loop_config(
            tmp_path, checks=[f"{sys.executable} {check_fixture}"]
        )

        (plan_dir / "example.md").write_text(
            "# Example 実装計画書\n\n## 3. 変更対象\n\n- `src/not-actually-changed.ts`\n",
            encoding="utf-8",
        )
        tracked_file.write_text("export const tracked = 1;\n", encoding="utf-8")

        cwd = str(tmp_path)
        _expect_command_to_succeed("git init", cwd)
        _expect_command_to_succeed(
            "git config user.email test@example.com && git config user.name 'Test User'",
            cwd,
        )
        _expect_command_to_succeed("git add . && git commit -m 'initial'", cwd)

        tracked_file.write_text("export const tracked = 2;\n", encoding="utf-8")
        untracked_file.write_text(
            "export const untracked = true;\n", encoding="utf-8"
        )

        completed = run_code_review(
            check_commands=[],
            plan_path="docs/implementation-plans/example.md",
            repo_path=cwd,
            reviewer_command=_build_reviewer_assertion_command(
                changed_files=["src/tracked.ts", "src/untracked.ts"],
                checks_run=[f"{sys.executable} {check_fixture}"],
                fixture_path=reviewer_fixture,
            ),
        )

        assert completed.output.verdict == ReviewVerdict.APPROVE

    def test_falls_back_to_modified_files_when_not_git_repo(
        self, tmp_path: Path
    ) -> None:
        plan_dir = tmp_path / "docs" / "implementation-plans"
        source_dir = tmp_path / "src"
        fixture_dir = Path(__file__).parent / "fixtures"
        reviewer_fixture = str(fixture_dir / "mock_one_shot_code_reviewer_assert.py")
        check_fixture = str(fixture_dir / "mock_check.py")

        plan_dir.mkdir(parents=True)
        source_dir.mkdir(parents=True)
        _write_compat_loop_config(
            tmp_path, checks=[f"{sys.executable} {check_fixture}"]
        )

        (plan_dir / "example.md").write_text(
            "# Example 実装計画書\n\n## 3. 変更対象\n\n- `src/not-actually-changed.ts`\n",
            encoding="utf-8",
        )

        # Wait briefly so mtime differs
        time.sleep(0.05)

        (source_dir / "actual-change.ts").write_text(
            "export const changed = true;\n", encoding="utf-8"
        )
        (tmp_path / "README.local.md").write_text("local change\n", encoding="utf-8")

        completed = run_code_review(
            check_commands=[],
            plan_path="docs/implementation-plans/example.md",
            repo_path=str(tmp_path),
            reviewer_command=_build_reviewer_assertion_command(
                changed_files=["README.local.md", "src/actual-change.ts"],
                checks_run=[f"{sys.executable} {check_fixture}"],
                fixture_path=reviewer_fixture,
            ),
        )

        assert completed.output.verdict == ReviewVerdict.APPROVE
