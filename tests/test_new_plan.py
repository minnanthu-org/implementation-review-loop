"""Tests for new_plan_cmd — matching new-plan.test.ts."""

import json
from pathlib import Path

from agent_loop.cli.new_plan_cmd import normalize_slug, scaffold_plan_files


class TestNormalizeSlug:
    def test_normalizes_slug_and_applies_defaults(self) -> None:
        assert normalize_slug("Run Loop Check Config") == "run-loop-check-config"

    def test_returns_none_for_empty(self) -> None:
        assert normalize_slug(None) is None
        assert normalize_slug("") is None

    def test_strips_leading_trailing_hyphens(self) -> None:
        assert normalize_slug("--foo--") == "foo"


class TestScaffoldPlanFiles:
    def test_creates_plan_and_review_files_from_templates(
        self, tmp_path: Path
    ) -> None:
        plan_template_dir = tmp_path / "docs" / "implementation-plans"
        review_template_dir = tmp_path / "docs" / "plan-reviews"
        config_dir = tmp_path / ".agent-loop"

        plan_template_dir.mkdir(parents=True)
        review_template_dir.mkdir(parents=True)
        config_dir.mkdir(parents=True)

        # Write repo config
        (config_dir / "config.json").write_text(
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
                    "execution": {"mode": "compat-loop", "provider": "codex"},
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        (plan_template_dir / "TEMPLATE.md").write_text(
            "# 実装計画書テンプレート\n\n状態: 下書き\n作成日: YYYY-MM-DD\n作成者: <name>\n",
            encoding="utf-8",
        )
        (review_template_dir / "TEMPLATE.md").write_text(
            "# 計画レビュー記録テンプレート\n\n状態: 下書き\nレビュー日: YYYY-MM-DD\nレビュー担当: <name>\n対象計画書: `docs/implementation-plans/<plan-file>.md`\n",
            encoding="utf-8",
        )

        created = scaffold_plan_files(
            author="Tester",
            date="2026-03-14",
            repo_path=str(tmp_path),
            slug="my-change",
            title="My Change",
        )

        plan = Path(created.plan_path).read_text(encoding="utf-8")
        review = Path(created.review_path).read_text(encoding="utf-8")

        assert "# My Change 実装計画書" in plan
        assert "状態: 下書き" in plan
        assert "作成日: 2026-03-14" in plan
        assert "作成者: Tester" in plan
        assert "# My Change 計画レビュー記録" in review
        assert "状態: 下書き" in review
        assert "レビュー日: 未定" in review
        assert (
            "対象計画書: `docs/implementation-plans/20260314-my-change.md`"
            in review
        )
