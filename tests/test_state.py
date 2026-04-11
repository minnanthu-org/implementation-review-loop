"""Tests for run_loop.state helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from agent_loop.core.run_loop.state import build_run_id, format_timestamp


class TestBuildRunId:
    def test_includes_plan_stem_and_timestamp(self) -> None:
        now = datetime(2026, 4, 12, 14, 30, 45, tzinfo=timezone.utc)
        run_id = build_run_id("docs/plans/20260412-my-plan.md", now)
        assert run_id.startswith(f"{format_timestamp(now)}-20260412-my-plan-")

    def test_unique_for_same_timestamp_and_plan(self) -> None:
        """Two runs started in the same second must get distinct IDs.

        Regression test for the second-precision collision bug: the old
        implementation returned the same run ID for two calls with identical
        (plan, timestamp), which caused silent state-mixing when the same
        plan was started twice in the same second.
        """
        now = datetime(2026, 4, 12, 14, 30, 45, tzinfo=timezone.utc)
        plan = "docs/plans/20260412-my-plan.md"
        first = build_run_id(plan, now)
        second = build_run_id(plan, now)
        assert first != second

    def test_suffix_survives_empty_plan_stem(self) -> None:
        now = datetime(2026, 4, 12, 14, 30, 45, tzinfo=timezone.utc)
        # All-punctuation stem collapses to empty and falls back to "plan".
        run_id = build_run_id("---.md", now)
        assert "-plan-" in run_id
        # And is still unique across calls.
        assert run_id != build_run_id("---.md", now)
