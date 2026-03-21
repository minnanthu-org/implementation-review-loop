"""Tests for the run-loop — ported from run-loop.test.ts."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_loop.core.run_loop import RunLoopOptions, initialize_run, run_loop
from agent_loop.core.run_loop.summary import format_duration

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
        "runDir": ".agent-loop/runs",
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

    def test_timing_data_on_approve(self, tmp_path: Path) -> None:
        """Approved run returns deterministic timing values for each attempt."""
        repo_dir = str(tmp_path)
        plan_dir = tmp_path / "docs" / "implementation-plans"
        plan_dir.mkdir(parents=True)
        _write_compat_loop_config(repo_dir)
        (plan_dir / "example.md").write_text("# Approved Plan\n", encoding="utf-8")

        # Deterministic monotonic clock: increments by 10s per call
        tick = iter(range(0, 10000, 10))

        python = sys.executable
        with patch("agent_loop.core.run_loop.loop.time") as mock_time:
            mock_time.monotonic = lambda: next(tick)
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

        assert completed.state.status.value == "approved"
        assert len(completed.timing) == 2

        # Each phase gets exactly 10s (two monotonic() calls per phase, 10 apart)
        t1 = completed.timing[0]
        assert t1["attempt"] == 1
        assert t1["implement"] == 10.0
        assert t1["check"] == 10.0
        assert t1["review"] == 10.0

        t2 = completed.timing[1]
        assert t2["attempt"] == 2
        assert t2["implement"] == 10.0
        assert t2["check"] == 10.0
        assert t2["review"] == 10.0

        # Verify summary.md contains deterministic timing values
        summary = (Path(completed.runDir) / "summary.md").read_text(encoding="utf-8")
        assert "## 所要時間" in summary
        assert "| Attempt | Implement | Check | Review | Total |" in summary
        # Each attempt row: 10s per phase, 30s total
        assert "| 1 | 10s | 10s | 10s | 30s |" in summary
        assert "| 2 | 10s | 10s | 10s | 30s |" in summary
        # Totals row: 20s per phase, 60s = 1m 00s grand total
        assert "| **Total** | 20s | 20s | 20s | 1m 00s |" in summary

    def test_timing_data_on_replan(self, tmp_path: Path) -> None:
        """Replan exit records implement only; check and review are None."""
        repo_dir = str(tmp_path)
        plan_dir = tmp_path / "docs" / "implementation-plans"
        plan_dir.mkdir(parents=True)
        _write_compat_loop_config(repo_dir)
        (plan_dir / "example.md").write_text("# Replan Plan\n", encoding="utf-8")

        tick = iter(range(0, 10000, 10))

        python = sys.executable
        with patch("agent_loop.core.run_loop.loop.time") as mock_time:
            mock_time.monotonic = lambda: next(tick)
            completed = run_loop(
                RunLoopOptions(
                    checkCommands=[
                        f"{python} {Path(FIXTURE_DIR) / 'mock_check.py'}"
                    ],
                    codeReviewSchemaPath=_DUMMY_SCHEMA,
                    implementerCommand=f"{python} {Path(FIXTURE_DIR) / 'mock_replan_implementer.py'}",
                    implementerSchemaPath=_DUMMY_SCHEMA,
                    planPath="docs/implementation-plans/example.md",
                    repoPath=repo_dir,
                    reviewerCommand=f"{python} {Path(FIXTURE_DIR) / 'mock_reviewer.py'}",
                )
            )

        assert completed.state.status.value == "needs-replan"
        assert len(completed.timing) == 1

        t = completed.timing[0]
        assert t["attempt"] == 1
        assert t["implement"] == 10.0
        assert t["check"] is None
        assert t["review"] is None

        # Verify summary.md timing shows "-" for unexecuted phases, deterministic values
        summary = (Path(completed.runDir) / "summary.md").read_text(encoding="utf-8")
        assert "## 所要時間" in summary
        assert "| 1 | 10s | - | - | 10s |" in summary
        assert "| **Total** | 10s | - | - | 10s |" in summary


class TestTimingCli:
    def test_print_timing_table_approve(self) -> None:
        """_print_timing_table outputs correct box-drawing table to stderr."""
        import io

        from agent_loop.cli.run_loop_cmd import _print_timing_table

        timing = [
            {"attempt": 1, "implement": 10.0, "check": 10.0, "review": 10.0},
            {"attempt": 2, "implement": 10.0, "check": 10.0, "review": 10.0},
        ]

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            _print_timing_table(timing)

        output = captured.getvalue()
        assert "Attempt" in output
        assert "Implement" in output
        assert "10s" in output
        assert "Total" in output
        # Box-drawing characters
        assert "┌" in output
        assert "└" in output

    def test_print_timing_table_replan(self) -> None:
        """_print_timing_table shows dashes for None phases."""
        import io

        from agent_loop.cli.run_loop_cmd import _print_timing_table

        timing = [
            {"attempt": 1, "implement": 10.0, "check": None, "review": None},
        ]

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            _print_timing_table(timing)

        output = captured.getvalue()
        assert "10s" in output
        assert "-" in output
        assert "Total" in output


class TestFormatDuration:
    def test_none_returns_dash(self) -> None:
        assert format_duration(None) == "-"

    def test_seconds_only(self) -> None:
        assert format_duration(45.0) == "45s"

    def test_minutes_and_seconds(self) -> None:
        assert format_duration(150.0) == "2m 30s"

    def test_zero(self) -> None:
        assert format_duration(0.0) == "0s"
