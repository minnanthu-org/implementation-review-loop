"""Tests for plan_review_cmd."""

import json
import os
import sys
from pathlib import Path

import pytest

from agent_loop.cli.plan_review_cmd import (
    build_plan_review_prompt,
    load_plan_reviewer_rules,
    render_plan_review_record,
    run_plan_review,
)
from agent_loop.core.contracts import (
    PlanReviewConclusion,
    PlanReviewFinding,
    PlanReviewFindingSeverity,
    PlanReviewFindingType,
    PlanReviewOutput,
)
from agent_loop.core.repo_config import DelegatedRepoConfig


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


def _delegated_config(rules_path: str | None = None) -> DelegatedRepoConfig:
    return DelegatedRepoConfig.model_validate(
        {
            "configVersion": 1,
            "plansDir": "docs/implementation-plans",
            "reviewsDir": "docs/plan-reviews",
            "planReviewerRules": rules_path,
            "execution": {"mode": "delegated", "provider": "codex"},
        }
    )


class TestLoadPlanReviewerRules:
    def test_returns_none_when_not_configured(self, tmp_path: Path) -> None:
        assert load_plan_reviewer_rules(str(tmp_path), _delegated_config()) is None

    def test_fails_when_configured_file_is_missing(self, tmp_path: Path) -> None:
        config = _delegated_config(".agent-loop/prompts/plan-reviewer-rules.md")

        with pytest.raises(FileNotFoundError, match="Missing planReviewerRules"):
            load_plan_reviewer_rules(str(tmp_path), config)

    def test_returns_none_when_file_has_only_comments(self, tmp_path: Path) -> None:
        rules = tmp_path / "rules.md"
        rules.write_text(
            "<!--\n記入例:\n\n## 絶対制約\n\n- dry_run=true を既定にする\n-->\n",
            encoding="utf-8",
        )

        assert (
            load_plan_reviewer_rules(str(tmp_path), _delegated_config("rules.md"))
            is None
        )

    def test_fails_on_unclosed_comment(self, tmp_path: Path) -> None:
        rules = tmp_path / "rules.md"
        rules.write_text(
            "<!--\n雛形の説明\n\n## 絶対制約\n\n- dry_run=true を既定にする\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="Unbalanced HTML comment"):
            load_plan_reviewer_rules(str(tmp_path), _delegated_config("rules.md"))

    def test_fails_on_stray_comment_closer(self, tmp_path: Path) -> None:
        rules = tmp_path / "rules.md"
        rules.write_text(
            "## 状態遷移\n\n申請 --> 承認 の直行を禁止する\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="Unbalanced HTML comment"):
            load_plan_reviewer_rules(str(tmp_path), _delegated_config("rules.md"))

    def test_returns_content_with_comments_stripped(self, tmp_path: Path) -> None:
        rules = tmp_path / "rules.md"
        rules.write_text(
            "<!-- 雛形の説明 -->\n## 絶対制約\n\n- dry_run=true を既定にする\n",
            encoding="utf-8",
        )

        loaded = load_plan_reviewer_rules(str(tmp_path), _delegated_config("rules.md"))

        assert loaded == "## 絶対制約\n\n- dry_run=true を既定にする"


class TestBuildPlanReviewPrompt:
    def test_injects_project_rules_section(self) -> None:
        prompt = build_plan_review_prompt(
            plan_contents="# Example 実装計画書",
            plan_path="docs/implementation-plans/example.md",
            prompt_template="# Plan Reviewer",
            repo_config=_delegated_config("rules.md"),
            output_schema="{}",
            project_rules="## 絶対制約\n\n- dry_run=true を既定にする",
        )

        assert "## プロジェクト固有レビュールール" in prompt
        assert "- dry_run=true を既定にする" in prompt
        assert prompt.index("## プロジェクト固有レビュールール") < prompt.index(
            "## 対象計画書パス"
        )

    def test_omits_project_rules_section_when_absent(self) -> None:
        prompt = build_plan_review_prompt(
            plan_contents="# Example 実装計画書",
            plan_path="docs/implementation-plans/example.md",
            prompt_template="# Plan Reviewer",
            repo_config=_delegated_config(),
            output_schema="{}",
        )

        assert "## プロジェクト固有レビュールール" not in prompt


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

    def test_passes_project_rules_to_reviewer_prompt(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "docs" / "implementation-plans"
        config_dir = tmp_path / ".agent-loop"
        prompts_dir = config_dir / "prompts"
        capture_path = tmp_path / "captured-prompt.txt"
        fixture_path = str(
            Path(__file__).parent / "fixtures" / "mock_plan_reviewer_capture.py"
        )

        plan_dir.mkdir(parents=True)
        prompts_dir.mkdir(parents=True)

        (config_dir / "config.json").write_text(
            json.dumps(
                {
                    "configVersion": 1,
                    "plansDir": "docs/implementation-plans",
                    "reviewsDir": "docs/plan-reviews",
                    "planReviewerRules": ".agent-loop/prompts/plan-reviewer-rules.md",
                    "execution": {"mode": "delegated", "provider": "codex"},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (prompts_dir / "plan-reviewer-rules.md").write_text(
            "<!-- 雛形の説明 -->\n## 絶対制約\n\n- dry_run=true を既定にする\n",
            encoding="utf-8",
        )
        (plan_dir / "example.md").write_text(
            "# Example 実装計画書\n\n状態: 下書き\n",
            encoding="utf-8",
        )

        run_plan_review(
            plan_path="docs/implementation-plans/example.md",
            repo_path=str(tmp_path),
            reviewer_command=(
                f"PROMPT_CAPTURE_PATH='{capture_path}' "
                f"{sys.executable} {fixture_path}"
            ),
        )

        captured = capture_path.read_text(encoding="utf-8")

        assert "## プロジェクト固有レビュールール" in captured
        assert "- dry_run=true を既定にする" in captured
        assert "雛形の説明" not in captured
