"""agent-loop plan review — plan review workflow."""

from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import click

from agent_loop.cli.assets import resolve_asset_path
from agent_loop.cli.formatting import (
    extract_plan_title,
    fenced_json,
    format_provider_display_name,
    format_tokyo_date,
)
from agent_loop.core.contracts import PlanReviewOutput
from agent_loop.core.process import ensure_successful_command
from agent_loop.core.providers import check_provider_available
from agent_loop.core.providers.structured_prompt import run_structured_prompt
from agent_loop.core.repo_config import (
    RepoConfig,
    WorkflowProvider,
    get_effective_model,
    get_effective_provider,
    load_repo_config,
)

DEFAULT_REVIEWER_NAME = "Codex"


@dataclass(frozen=True)
class CompletedPlanReview:
    output: PlanReviewOutput
    review_path: str


def run_plan_review(
    *,
    model: str | None = None,
    plan_path: str,
    repo_path: str,
    review_path: str | None = None,
    reviewer_command: str | None = None,
    provider: WorkflowProvider | None = None,
) -> CompletedPlanReview:
    """Execute a plan review and write the review record."""
    resolved_repo = str(Path(repo_path).resolve())
    repo_config = load_repo_config(resolved_repo)
    resolved_plan = str(Path(resolved_repo, plan_path).resolve())

    if review_path:
        resolved_review = str(Path(resolved_repo, review_path).resolve())
    else:
        resolved_review = str(
            Path(
                resolved_repo,
                repo_config.reviewsDir,
                f"{Path(resolved_plan).stem}-review.md",
            )
        )

    prompt_path = resolve_asset_path("prompts", "plan-reviewer.md")
    schema_path = resolve_asset_path("schemas", "plan-review-output.schema.json")

    plan_contents = Path(resolved_plan).read_text(encoding="utf-8")
    prompt_template = Path(prompt_path).read_text(encoding="utf-8")
    output_schema = Path(schema_path).read_text(encoding="utf-8")

    plan_path_relative = str(
        Path(resolved_plan).relative_to(resolved_repo)
    ).replace("\\", "/")

    prompt = build_plan_review_prompt(
        plan_contents=plan_contents,
        plan_path=plan_path_relative,
        prompt_template=prompt_template,
        repo_config=repo_config,
        output_schema=output_schema,
    )

    temp_dir = tempfile.mkdtemp(prefix="agent-loop-plan-review-")
    output_path = str(Path(temp_dir) / "plan-review-output.json")

    reviewer_provider = provider or get_effective_provider(repo_config.execution)
    if not reviewer_command:
        check_provider_available(reviewer_provider)
    reviewer_model = model or get_effective_model(repo_config.execution)
    reviewer_name = format_provider_display_name(reviewer_provider)

    result = run_structured_prompt(
        command=reviewer_command,
        cwd=resolved_repo,
        env={
            "PLAN_REVIEW_OUTPUT_PATH": output_path,
            "PLAN_REVIEW_PLAN_PATH": resolved_plan,
            "PLAN_REVIEW_REPO_PATH": resolved_repo,
        },
        model=reviewer_model,
        output_path=output_path,
        prompt=prompt,
        provider=reviewer_provider,
        schema_path=schema_path,
    )

    ensure_successful_command("Plan Reviewer", result)

    output = PlanReviewOutput.model_validate(
        json.loads(Path(output_path).read_text(encoding="utf-8"))
    )
    _validate_plan_review_output(output)

    Path(resolved_review).parent.mkdir(parents=True, exist_ok=True)
    Path(resolved_review).write_text(
        render_plan_review_record(
            output=output,
            plan_path=plan_path_relative,
            review_date=format_tokyo_date(),
            reviewer_name=reviewer_name,
            title=extract_plan_title(plan_contents, resolved_plan),
        ),
        encoding="utf-8",
    )

    return CompletedPlanReview(output=output, review_path=resolved_review)


def render_plan_review_record(
    *,
    output: PlanReviewOutput,
    plan_path: str,
    review_date: str,
    reviewer_name: str | None = None,
    title: str,
) -> str:
    """Render a plan review record Markdown document."""
    lines = [
        f"# {title} 計画レビュー記録",
        "",
        f"状態: {_map_conclusion_to_document_status(output.conclusion.value)}",
        f"レビュー日: {review_date}",
        f"レビュー担当: {reviewer_name or DEFAULT_REVIEWER_NAME}",
        f"対象計画書: `{plan_path}`",
        "",
        "## 1. 結論",
        "",
        f"- `{output.conclusion.value}`",
        "",
        "## 2. 総評",
        "",
        output.summaryMd.strip(),
        "",
        "## 3. 指摘一覧",
        "",
    ]

    if len(output.findings) == 0:
        lines.extend(["なし", ""])
    else:
        for finding in output.findings:
            lines.extend([
                f"### {finding.id}",
                "",
                f"- 種別: `{finding.type.value}`",
                f"- 重大度: `{finding.severity.value}`",
                f"- 内容: {finding.contentMd}",
                f"- 修正案: {finding.suggestedFixMd}",
                "",
            ])

    lines.extend([
        "## 4. 影響範囲レビュー",
        "",
        output.impactReviewMd.strip(),
        "",
        "## 5. checks レビュー",
        "",
        output.checksReviewMd.strip(),
        "",
        "## 6. 人間判断が必要な点",
        "",
        output.humanJudgementMd.strip(),
        "",
        "## 7. 再レビュー条件",
        "",
        output.reReviewConditionMd.strip(),
        "",
    ])

    return "\n".join(lines) + "\n"


def build_plan_review_prompt(
    *,
    plan_contents: str,
    plan_path: str,
    prompt_template: str,
    repo_config: RepoConfig,
    output_schema: str,
) -> str:
    """Build the plan review prompt."""
    repo_config_json = json.dumps(repo_config.model_dump(), indent=2)

    return "\n\n".join([
        prompt_template.strip(),
        "## 対象計画書パス",
        plan_path,
        "## 対象計画書",
        plan_contents.strip(),
        "## Repo 設定 JSON",
        fenced_json(repo_config_json),
        "## 追加指示",
        "必要なら計画書が参照するコード、直近の呼び出し元、関連テスト、既存テンプレートを repo 内で読んでください。\n"
        "コード変更は行わず、計画の妥当性だけを評価してください。",
        "## 出力 JSON Schema",
        fenced_json(output_schema),
        "\n".join([
            "## [重要] 出力形式",
            "",
            "**必ず JSON 形式のみで出力してください。**",
            "",
            "- 上記 JSON Schema に厳密に一致する JSON オブジェクトだけを返すこと",
            "- JSON の前後にテキスト・説明・挨拶・要約を絶対に付けないこと",
            "- コードブロック (```) で囲まないこと",
            "- 出力の最初の文字は `{`、最後の文字は `}` であること",
            "- JSON のキー名は schema の `properties` に記載されたとおりに保ち、人間向けの Markdown 文字列は日本語で書くこと",
        ]),
    ])


def _validate_plan_review_output(output: PlanReviewOutput) -> None:
    if output.conclusion.value == "approve" and len(output.findings) > 0:
        raise ValueError("Plan Reviewer cannot approve while findings remain")
    if output.conclusion.value == "needs-fix" and len(output.findings) == 0:
        raise ValueError("Plan Reviewer must report findings on needs-fix")


def _map_conclusion_to_document_status(conclusion: str) -> str:
    return "承認済み" if conclusion == "approve" else "レビュー済み"


@click.command("review")
@click.option("--plan", "plan_path", required=True, help="Path to the plan file.")
@click.option("--repo", default=".", type=click.Path(exists=False), help="Repository path.")
@click.option("--review", "review_path", default=None, help="Output review file path.")
@click.option("--reviewer-command", default=None, help="Custom reviewer command.")
@click.option("--provider", default=None, type=click.Choice(["codex", "claude", "gemini"]), help="Reviewer provider.")
@click.option("--model", default=None, help="Model to use (e.g. sonnet, gpt-5.4, gemini-2.5-pro).")
def plan_review_command(
    plan_path: str,
    repo: str,
    review_path: str | None,
    reviewer_command: str | None,
    provider: str | None,
    model: str | None,
) -> None:
    """Review an implementation plan."""
    completed = run_plan_review(
        model=model,
        plan_path=plan_path,
        repo_path=repo,
        review_path=review_path,
        reviewer_command=reviewer_command,
        provider=WorkflowProvider(provider) if provider else None,
    )

    click.echo(f"[INFO] Created plan review: {completed.review_path}", err=True)
    sys.stdout.write(f"{completed.review_path}\n")
