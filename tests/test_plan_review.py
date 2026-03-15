"""Tests for plan_review_cmd."""

import json
import os
import sys
from pathlib import Path

from agent_loop.cli.plan_review_cmd import render_plan_review_record, run_plan_review
from agent_loop.core.contracts import (
    PlanReviewConclusion,
    PlanReviewFinding,
    PlanReviewFindingSeverity,
    PlanReviewFindingType,
    PlanReviewOutput,
)


class TestRenderPlanReviewRecord:
    def test_renders_review_record_matching_template_sections(self) -> None:
        review = render_plan_review_record(
            output=PlanReviewOutput(
                conclusion=PlanReviewConclusion.NEEDS_FIX,
                summaryMd="checks の定義が曖昧です。",
                findings=[
                    PlanReviewFinding(
                        id="PR-001",
                        type=PlanReviewFindingType.MISSING_CHECK,
                        severity=PlanReviewFindingSeverity.MEDIUM,
                        contentMd="必須 checks に `npm test` がありません。",
                        suggestedFixMd="`npm test` を追加してください。",
                    ),
                ],
                impactReviewMd="- 変更対象は概ね妥当",
                checksReviewMd="- `npm run build`\n- `npm test` が必要",
                humanJudgementMd="なし",
                reReviewConditionMd="checks が補強されたら再レビュー可能",
            ),
            plan_path="docs/implementation-plans/example.md",
            review_date="2026-03-14",
            title="Example",
        )

        assert "# Example 計画レビュー記録" in review
        assert "状態: レビュー済み" in review
        assert "- `needs-fix`" in review
        assert "### PR-001" in review
        assert "## 5. checks レビュー" in review


class TestRunPlanReview:
    def test_writes_delegated_plan_review_record(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "docs" / "implementation-plans"
        config_dir = tmp_path / ".agent-loop"
        fixture_path = str(
            Path(__file__).parent / "fixtures" / "mock_plan_reviewer.py"
        )

        plan_dir.mkdir(parents=True)
        config_dir.mkdir(parents=True)

        (config_dir / "config.json").write_text(
            json.dumps(
                {
                    "configVersion": 1,
                    "plansDir": "docs/implementation-plans",
                    "reviewsDir": "docs/plan-reviews",
                    "execution": {"mode": "delegated", "provider": "codex"},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (plan_dir / "example.md").write_text(
            "# Example 実装計画書\n\n状態: 下書き\n",
            encoding="utf-8",
        )

        completed = run_plan_review(
            plan_path="docs/implementation-plans/example.md",
            repo_path=str(tmp_path),
            reviewer_command=f"{sys.executable} {fixture_path}",
        )

        review = Path(completed.review_path).read_text(encoding="utf-8")

        assert completed.output.conclusion == PlanReviewConclusion.APPROVE
        assert completed.review_path == str(
            tmp_path / "docs" / "plan-reviews" / "example-review.md"
        )
        assert "# Example 計画レビュー記録" in review
        assert "状態: 承認済み" in review
        assert "- `approve`" in review
        assert "対象計画書: `docs/implementation-plans/example.md`" in review
