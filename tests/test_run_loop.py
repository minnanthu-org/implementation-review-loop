"""Tests for the run-loop — ported from run-loop.test.ts."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from agent_loop.core.run_loop import RunLoopOptions, initialize_run, run_loop

FIXTURE_DIR = str(Path(__file__).resolve().parent / "fixtures")


def _write_compat_loop_config(
    repo_dir: str,
    *,
    checks: list[str] | None = None,
    provider: str = "codex",
) -> None:
    """Write a minimal .agent-loop config tree for testing."""
    agent_loop_dir = Path(repo_dir) / ".agent-loop"
    prompt_dir = agent_loop_dir / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)

    config = {
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
            "defaultProvider": provider,
        },
    }

    (agent_loop_dir / "config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )
    (agent_loop_dir / "checks.json").write_text(
        json.dumps({"commands": list(checks or [])}, indent=2), encoding="utf-8"
    )
    (prompt_dir / "implementer.md").write_text("# Implementer\n", encoding="utf-8")
    (prompt_dir / "code-reviewer.md").write_text("# Code Reviewer\n", encoding="utf-8")


# --- Dummy schema path (the core loop only passes it through) ---
_DUMMY_SCHEMA = str(Path(FIXTURE_DIR) / "mock_check.py")  # any existing file


class TestInitializeRun:
    def test_rejects_nested_workflow_invocation(self, tmp_path: Path) -> None:
        repo_dir = str(tmp_path)
        plan_dir = tmp_path / "docs" / "implementation-plans"
        plan_dir.mkdir(parents=True)
        _write_compat_loop_config(repo_dir)
        (plan_dir / "example.md").write_text("# Plan\n", encoding="utf-8")

        original = os.environ.get("WORKFLOW_ACTIVE_COMMAND")
        os.environ["WORKFLOW_ACTIVE_COMMAND"] = "code:review"

        try:
            with pytest.raises(
                RuntimeError,
                match="Nested workflow invocation is not allowed: attempted loop:run while code:review is already running.",
            ):
                initialize_run(
                    RunLoopOptions(
                        checkCommands=[],
                        codeReviewSchemaPath=_DUMMY_SCHEMA,
                        implementerCommand="echo noop",
                        implementerSchemaPath=_DUMMY_SCHEMA,
                        planPath="docs/implementation-plans/example.md",
                        repoPath=repo_dir,
                        reviewerCommand="echo noop",
                    )
                )
        finally:
            if original is None:
                os.environ.pop("WORKFLOW_ACTIVE_COMMAND", None)
            else:
                os.environ["WORKFLOW_ACTIVE_COMMAND"] = original

    def test_creates_run_directory_with_copied_plan_and_state(
        self, tmp_path: Path
    ) -> None:
        repo_dir = str(tmp_path)
        plan_dir = tmp_path / "docs" / "implementation-plans"
        plan_dir.mkdir(parents=True)
        _write_compat_loop_config(repo_dir)
        (plan_dir / "example.md").write_text("# Plan\n", encoding="utf-8")

        initialized = initialize_run(
            RunLoopOptions(
                checkCommands=[],
                codeReviewSchemaPath=_DUMMY_SCHEMA,
                implementerCommand="echo noop",
                implementerSchemaPath=_DUMMY_SCHEMA,
                planPath="docs/implementation-plans/example.md",
                repoPath=repo_dir,
                reviewerCommand="echo noop",
            )
        )

        copied_plan = Path(initialized.state.localPlanPath).read_text(encoding="utf-8")
        state_json = json.loads(
            (Path(initialized.runDir) / "state.json").read_text(encoding="utf-8")
        )
        finding_ledger_json = json.loads(
            (Path(initialized.runDir) / "finding-ledger.json").read_text(
                encoding="utf-8"
            )
        )
        summary = (Path(initialized.runDir) / "summary.md").read_text(
            encoding="utf-8"
        )

        assert copied_plan == "# Plan\n"
        assert state_json["status"] == "initialized"
        assert state_json["maxAttempts"] == 3
        assert state_json["findingLedgerPath"] == str(
            Path(initialized.runDir) / "finding-ledger.json"
        )
        assert os.path.join(".agent-loop", "prompts", "implementer.md") in state_json[
            "implementerPromptPath"
        ]
        assert finding_ledger_json == []
        assert "状態: `initialized`" in summary
        assert "## 最新の Implementer 要約" in summary

    def test_merges_repo_plan_and_cli_checks(
        self, tmp_path: Path
    ) -> None:
        repo_dir = str(tmp_path)
        plan_dir = tmp_path / "docs" / "implementation-plans"
        plan_dir.mkdir(parents=True)
        _write_compat_loop_config(repo_dir, checks=["npm run lint", "npm test"])
        (plan_dir / "example.md").write_text(
            """# Plan

## 9. 必須 checks

- `pytest -q`
- `npm test`
""",
            encoding="utf-8",
        )

        initialized = initialize_run(
            RunLoopOptions(
                checkCommands=["npm test", "npm run typecheck"],
                codeReviewSchemaPath=_DUMMY_SCHEMA,
                implementerCommand="echo noop",
                implementerSchemaPath=_DUMMY_SCHEMA,
                planPath="docs/implementation-plans/example.md",
                repoPath=repo_dir,
                reviewerCommand="echo noop",
            )
        )

        assert initialized.state.checkCommands == [
            "npm run lint",
            "npm test",
            "pytest -q",
            "npm run typecheck",
        ]
        assert initialized.state.checksFilePath == str(
            Path(repo_dir) / ".agent-loop" / "checks.json"
        )


class TestRunLoop:
    def test_runs_implementer_and_reviewer_until_approval(
        self, tmp_path: Path
    ) -> None:
        repo_dir = str(tmp_path)
        plan_dir = tmp_path / "docs" / "implementation-plans"
        plan_dir.mkdir(parents=True)
        _write_compat_loop_config(repo_dir)
        (plan_dir / "example.md").write_text("# Approved Plan\n", encoding="utf-8")

        python = sys.executable
        completed = run_loop(
            RunLoopOptions(
                checkCommands=[
                    f"{python} {Path(FIXTURE_DIR) / 'mock_check.py'}"
                ],
                codeReviewSchemaPath=_DUMMY_SCHEMA,
                implementerCommand=f"{python} {Path(FIXTURE_DIR) / 'mock_implementer.py'}",
                implementerSchemaPath=_DUMMY_SCHEMA,
                planPath="docs/implementation-plans/example.md",
                repoPath=repo_dir,
                reviewerCommand=f"{python} {Path(FIXTURE_DIR) / 'mock_reviewer.py'}",
            )
        )

        state_json = json.loads(
            (Path(completed.runDir) / "state.json").read_text(encoding="utf-8")
        )
        first_review = json.loads(
            (Path(completed.runDir) / "reviews" / "001.json").read_text(
                encoding="utf-8"
            )
        )
        second_review = json.loads(
            (Path(completed.runDir) / "reviews" / "002.json").read_text(
                encoding="utf-8"
            )
        )
        second_attempt = json.loads(
            (Path(completed.runDir) / "responses" / "002.json").read_text(
                encoding="utf-8"
            )
        )
        ledger = json.loads(
            (Path(completed.runDir) / "finding-ledger.json").read_text(
                encoding="utf-8"
            )
        )
        summary = (Path(completed.runDir) / "summary.md").read_text(
            encoding="utf-8"
        )

        assert completed.state.status.value == "approved"
        assert state_json["currentAttempt"] == 2
        assert first_review["verdict"] == "fix"
        assert second_review["verdict"] == "approve"
        assert second_attempt["responses"][0]["findingId"] == "F-001"
        assert ledger == [
            {
                "id": "F-001",
                "firstSeenAttempt": 1,
                "lastReviewedAttempt": 2,
                "currentSeverity": "high",
                "currentStatus": "closed",
                "summaryMd": "Null guard is now present.",
                "suggestedActionMd": "No further action required.",
                "reviewHistory": [
                    {
                        "attempt": 1,
                        "severity": "high",
                        "status": "open",
                        "summaryMd": "Add a null guard before dereferencing.",
                        "suggestedActionMd": "Handle null input before access.",
                        "verdict": "fix",
                    },
                    {
                        "attempt": 2,
                        "severity": "high",
                        "status": "closed",
                        "summaryMd": "Null guard is now present.",
                        "suggestedActionMd": "No further action required.",
                        "verdict": "approve",
                    },
                ],
                "responseHistory": [
                    {
                        "attempt": 2,
                        "responseType": "fixed",
                        "noteMd": "Resolved F-001.",
                    },
                ],
            },
        ]
        assert "状態: `approved`" in summary
        assert "解消済み finding 数: 1" in summary
        assert "## 最新の Review 要約" in summary
        assert "All findings are resolved." in summary
