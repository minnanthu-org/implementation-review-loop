"""agent-loop code review — one-shot code review workflow."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import click

from agent_loop.cli.agent_commands import default_reviewer_command
from agent_loop.cli.assets import resolve_asset_path
from agent_loop.cli.formatting import (
    extract_plan_title,
    format_provider_display_name,
    format_tokyo_date,
)
from agent_loop.core.checks import (
    CheckResult,
    resolve_configured_check_commands,
    run_checks,
)
from agent_loop.core.contracts import CodeReviewOutput
from agent_loop.core.nested_workflow_guard import (
    assert_no_nested_workflow_invocation,
    build_workflow_command_environment,
)
from agent_loop.core.process import (
    ensure_successful_command,
    run_shell_command,
)
from agent_loop.core.repo_config import (
    WorkflowProvider,
    load_compat_loop_repo_config,
)
from agent_loop.core.run_loop.io import write_json

DEFAULT_REVIEWER_NAME = "Codex"
DEFAULT_REVIEW_OUTPUT_DIR = str(Path("docs") / "implementation-reviews")
DEFAULT_AGENT_COMMAND_TIMEOUT_MS = 1_200_000
CHANGED_FILE_DETECTION_TIMEOUT_MS = 10_000
CHANGED_FILE_FALLBACK_EXCLUDED_DIRS = frozenset([
    ".git",
    ".loop",
    "dist",
    "node_modules",
])


@dataclass(frozen=True)
class CompletedCodeReview:
    check_results: list[CheckResult]
    output: CodeReviewOutput
    review_path: str


def run_code_review(
    *,
    check_commands: list[str],
    checks_file: str | None = None,
    plan_path: str,
    repo_path: str,
    review_path: str | None = None,
    reviewer_command: str | None = None,
    reviewer_provider: WorkflowProvider | None = None,
) -> CompletedCodeReview:
    """Execute a one-shot code review and write the review record."""
    assert_no_nested_workflow_invocation("code:review")

    resolved_repo = str(Path(repo_path).resolve())
    repo_config = load_compat_loop_repo_config(resolved_repo)
    resolved_plan = str(Path(resolved_repo, plan_path).resolve())

    if review_path:
        resolved_review = str(Path(resolved_repo, review_path).resolve())
    else:
        resolved_review = str(
            Path(
                resolved_repo,
                DEFAULT_REVIEW_OUTPUT_DIR,
                f"{Path(resolved_plan).stem}-implementation-review.md",
            )
        )

    checks_file_path = str(
        Path(resolved_repo) / (checks_file or repo_config.checksFile)
    )
    merged_check_commands = resolve_configured_check_commands(
        check_commands=check_commands,
        checks_file_path=checks_file_path,
    )
    check_results = run_checks(commands=merged_check_commands, cwd=resolved_repo)

    temp_dir = tempfile.mkdtemp(prefix="agent-loop-code-review-")
    review_output_path = str(Path(temp_dir) / "review-output.json")
    finding_ledger_path = str(Path(temp_dir) / "finding-ledger.json")
    open_findings_path = str(Path(temp_dir) / "open-findings.json")
    checks_path = str(Path(temp_dir) / "checks.json")
    implementer_output_path = str(Path(temp_dir) / "implementer-output.json")
    code_review_schema_path = resolve_asset_path(
        "schemas", "code-review-output.schema.json"
    )

    effective_reviewer_command = reviewer_command
    if not effective_reviewer_command and reviewer_provider:
        effective_reviewer_command = default_reviewer_command(reviewer_provider)

    if not effective_reviewer_command:
        raise click.UsageError(
            "--reviewer-provider is required (or use --reviewer-command)"
        )

    plan_contents = Path(resolved_plan).read_text(encoding="utf-8")
    review_date = format_tokyo_date()
    reviewer_name = format_provider_display_name(reviewer_provider)
    plan_path_relative = str(
        Path(resolved_plan).relative_to(resolved_repo)
    ).replace("\\", "/")
    changed_files = _collect_changed_files(
        plan_path=resolved_plan, repo_path=resolved_repo
    )

    write_json(finding_ledger_path, [])
    write_json(open_findings_path, [])
    write_json(checks_path, _build_check_results_for_reviewer(check_results))
    write_json(implementer_output_path, {
        "attempt": 1,
        "summaryMd": "One-shot code review request.",
        "changedFiles": changed_files,
        "checksRun": merged_check_commands,
        "responses": [],
        "replanRequired": False,
    })

    env = {
        **build_workflow_command_environment("code:review"),
        "WORKFLOW_REPO_PATH": resolved_repo,
        "WORKFLOW_RUN_DIR": temp_dir,
        "WORKFLOW_PLAN_PATH": resolved_plan,
        "WORKFLOW_REVIEW_RECORD_PATH": resolved_review,
        "WORKFLOW_ATTEMPT": "1",
        "WORKFLOW_OPEN_FINDINGS_PATH": open_findings_path,
        "WORKFLOW_FINDING_LEDGER_PATH": finding_ledger_path,
        "WORKFLOW_IMPLEMENTER_PROMPT_PATH": str(
            Path(resolved_repo) / repo_config.prompts.implementer
        ),
        "WORKFLOW_CODE_REVIEWER_PROMPT_PATH": str(
            Path(resolved_repo) / repo_config.prompts.reviewer
        ),
        "WORKFLOW_IMPLEMENTER_SCHEMA_PATH": resolve_asset_path(
            "schemas", "implementer-output.schema.json"
        ),
        "WORKFLOW_CODE_REVIEW_SCHEMA_PATH": code_review_schema_path,
        "WORKFLOW_IMPLEMENTER_OUTPUT_PATH": implementer_output_path,
        "WORKFLOW_CHECKS_PATH": checks_path,
        "WORKFLOW_CODE_REVIEW_OUTPUT_PATH": review_output_path,
    }

    reviewer_result = run_shell_command(
        command=effective_reviewer_command,
        cwd=resolved_repo,
        env=env,
        timeout_ms=DEFAULT_AGENT_COMMAND_TIMEOUT_MS,
    )

    ensure_successful_command("Code Reviewer", reviewer_result)

    output = CodeReviewOutput.model_validate(
        json.loads(Path(review_output_path).read_text(encoding="utf-8"))
    )
    _validate_one_shot_review_output(output)

    Path(resolved_review).parent.mkdir(parents=True, exist_ok=True)
    Path(resolved_review).write_text(
        render_code_review_record(
            check_results=check_results,
            output=output,
            plan_path=plan_path_relative,
            review_date=review_date,
            reviewer_name=reviewer_name,
            title=extract_plan_title(plan_contents, resolved_plan),
        ),
        encoding="utf-8",
    )

    return CompletedCodeReview(
        check_results=check_results,
        output=output,
        review_path=resolved_review,
    )


def render_code_review_record(
    *,
    check_results: list[CheckResult],
    output: CodeReviewOutput,
    plan_path: str,
    review_date: str,
    reviewer_name: str | None = None,
    title: str,
) -> str:
    """Render a code review record Markdown document."""
    lines = [
        f"# {title} 実装レビュー記録",
        "",
        "状態: レビュー済み",
        f"レビュー日: {review_date}",
        f"レビュー担当: {reviewer_name or DEFAULT_REVIEWER_NAME}",
        f"対象計画書: `{plan_path}`",
        f"結論: `{output.verdict.value}`",
        "",
        "## 総評",
        "",
        output.summaryMd.strip(),
        "",
        "## 指摘一覧",
        "",
    ]

    if len(output.findings) == 0:
        lines.extend(["なし", ""])
    else:
        for finding in output.findings:
            lines.extend([
                f"### {finding.id}",
                "",
                f"- 重大度: `{finding.severity.value}`",
                f"- 状態: `{finding.status.value}`",
                f"- 内容: {finding.summaryMd}",
                f"- 修正方向: {finding.suggestedActionMd}",
                "",
            ])

    lines.extend(["## checks", ""])

    if len(check_results) == 0:
        lines.extend(["_check command は設定されていません。_", ""])
    else:
        for result in check_results:
            label = "成功" if result.ok else "失敗"
            lines.append(f"- [{label}] `{result.command}`")
        lines.append("")

    lines.extend(["## 次に回すべき作業", ""])

    if output.verdict.value == "approve":
        lines.extend(["なし", ""])
    elif len(output.findings) == 0:
        lines.extend([output.summaryMd.strip(), ""])
    else:
        for finding in output.findings:
            if finding.status.value != "open":
                continue
            lines.append(f"- {finding.suggestedActionMd}")
        lines.append("")

    return "\n".join(lines) + "\n"


# --- Internal helpers ---


def _validate_one_shot_review_output(output: CodeReviewOutput) -> None:
    open_findings = [f for f in output.findings if f.status.value == "open"]
    if output.verdict.value == "approve" and len(open_findings) > 0:
        raise ValueError(
            "Code Reviewer cannot approve while open findings remain"
        )
    if output.verdict.value == "fix" and len(open_findings) == 0:
        raise ValueError(
            "Code Reviewer must keep at least one finding open on fix"
        )


def _collect_changed_files(
    *,
    plan_path: str,
    repo_path: str,
) -> list[str]:
    git_files = _collect_changed_files_from_git(repo_path)
    if git_files is not None:
        return git_files
    return _collect_changed_files_from_modified_time(
        plan_path=plan_path, repo_path=repo_path
    )


def _collect_changed_files_from_git(repo_path: str) -> list[str] | None:
    result = run_shell_command(
        command="git -c status.relativePaths=true -c status.renames=false status --short --untracked-files=all",
        cwd=repo_path,
        env=dict(os.environ),
        timeout_ms=CHANGED_FILE_DETECTION_TIMEOUT_MS,
    )

    if result.exit_code != 0:
        return None

    changed: set[str] = set()
    for line in result.stdout.split("\n"):
        if not line:
            continue
        candidate = line[3:].strip()
        if not candidate:
            continue
        changed.add(_normalize_repo_relative_path(_unquote_git_path(candidate)))

    return sorted(changed)


def _collect_changed_files_from_modified_time(
    *,
    plan_path: str,
    repo_path: str,
) -> list[str]:
    plan_mtime = Path(plan_path).stat().st_mtime
    changed: list[str] = []
    ignored = {
        _normalize_repo_relative_path(
            str(Path(plan_path).relative_to(repo_path))
        )
    }

    def walk(current: Path) -> None:
        for entry in sorted(current.iterdir()):
            if entry.is_dir():
                if entry.name in CHANGED_FILE_FALLBACK_EXCLUDED_DIRS:
                    continue
                walk(entry)
            elif entry.is_file():
                rel = _normalize_repo_relative_path(
                    str(entry.relative_to(repo_path))
                )
                if rel in ignored:
                    continue
                if entry.stat().st_mtime > plan_mtime:
                    changed.append(rel)

    walk(Path(repo_path))
    return sorted(changed)


def _normalize_repo_relative_path(value: str) -> str:
    return value.replace("\\", "/")


def _unquote_git_path(value: str) -> str:
    if not (value.startswith('"') and value.endswith('"')):
        return value
    return value[1:-1].replace("\\\\", "\\").replace('\\"', '"')


def _build_check_results_for_reviewer(
    check_results: list[CheckResult],
) -> dict[str, object]:
    return {
        "allPassed": all(r.ok for r in check_results),
        "attempt": 1,
        "commands": [
            {
                "command": r.command,
                "exitCode": r.exit_code,
                "ok": r.ok,
                "stdout": _summarize_check_stream(r.stdout, r.ok),
                "stderr": _summarize_check_stream(r.stderr, r.ok),
            }
            for r in check_results
        ],
    }


def _summarize_check_stream(value: str, ok: bool) -> str:
    trimmed = value.strip()
    if not trimmed:
        return ""
    if ok:
        return (
            f"{trimmed[:240]}\n... (truncated)" if len(trimmed) > 240 else trimmed
        )
    return (
        f"{trimmed[:1200]}\n... (truncated)" if len(trimmed) > 1200 else trimmed
    )


@click.command("review")
@click.option("--plan", "plan_path", required=True, help="Path to the plan file.")
@click.option("--repo", default=".", type=click.Path(exists=False), help="Repository path.")
@click.option("--review", "review_path", default=None, help="Output review file path.")
@click.option("--check-command", "check_commands", multiple=True, help="Check command(s).")
@click.option("--checks-file", default=None, help="Path to checks config file.")
@click.option("--reviewer-command", default=None, help="Custom reviewer command.")
@click.option("--provider", "provider_str", default=None, type=click.Choice(["codex", "claude", "gemini"]), help="Reviewer provider (alias for --reviewer-provider).")
@click.option("--reviewer-provider", default=None, type=click.Choice(["codex", "claude", "gemini"]), help="Reviewer provider.")
def code_review_command(
    plan_path: str,
    repo: str,
    review_path: str | None,
    check_commands: tuple[str, ...],
    checks_file: str | None,
    reviewer_command: str | None,
    provider_str: str | None,
    reviewer_provider: str | None,
) -> None:
    """Run a one-shot code review against an implementation plan."""
    effective_provider_str = reviewer_provider or provider_str
    effective_provider = (
        WorkflowProvider(effective_provider_str) if effective_provider_str else None
    )

    completed = run_code_review(
        check_commands=list(check_commands),
        checks_file=checks_file,
        plan_path=plan_path,
        repo_path=repo,
        review_path=review_path,
        reviewer_command=reviewer_command,
        reviewer_provider=effective_provider,
    )

    click.echo(
        f"[INFO] Created implementation review: {completed.review_path}", err=True
    )
    sys.stdout.write(f"{completed.review_path}\n")
