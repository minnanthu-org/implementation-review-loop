"""agent-loop agent run — unified workflow agent."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import click

from agent_loop.cli.formatting import fenced_json
from agent_loop.core.providers.structured_prompt import run_structured_prompt
from agent_loop.core.repo_config import WorkflowProvider

AgentRole = Literal["implementer", "reviewer"]


@dataclass(frozen=True)
class AgentContext:
    attempt: int
    checks_path: str | None
    code_reviewer_prompt_path: str
    code_review_schema_path: str
    finding_ledger_path: str
    implementer_output_path: str | None
    implementer_prompt_path: str
    implementer_schema_path: str
    open_findings_path: str
    output_path: str
    plan_path: str
    repo_path: str
    review_record_path: str | None
    run_dir: str


def load_context(role: AgentRole) -> AgentContext:
    """Load the agent context from WORKFLOW_* environment variables."""
    env = os.environ

    attempt = _require_env("WORKFLOW_ATTEMPT")
    code_reviewer_prompt_path = _require_env("WORKFLOW_CODE_REVIEWER_PROMPT_PATH")
    code_review_schema_path = _require_env("WORKFLOW_CODE_REVIEW_SCHEMA_PATH")
    implementer_prompt_path = _require_env("WORKFLOW_IMPLEMENTER_PROMPT_PATH")
    implementer_schema_path = _require_env("WORKFLOW_IMPLEMENTER_SCHEMA_PATH")
    finding_ledger_path = _require_env("WORKFLOW_FINDING_LEDGER_PATH")
    open_findings_path = _require_env("WORKFLOW_OPEN_FINDINGS_PATH")
    plan_path = _require_env("WORKFLOW_PLAN_PATH")
    repo_path = _require_env("WORKFLOW_REPO_PATH")
    run_dir = _require_env("WORKFLOW_RUN_DIR")

    if role == "implementer":
        output_path = env.get("WORKFLOW_IMPLEMENTER_OUTPUT_PATH")
    else:
        output_path = env.get("WORKFLOW_CODE_REVIEW_OUTPUT_PATH")

    if not output_path:
        raise RuntimeError("Missing required output path environment variable")

    return AgentContext(
        attempt=int(attempt),
        checks_path=env.get("WORKFLOW_CHECKS_PATH"),
        code_reviewer_prompt_path=code_reviewer_prompt_path,
        code_review_schema_path=code_review_schema_path,
        finding_ledger_path=finding_ledger_path,
        implementer_output_path=env.get("WORKFLOW_IMPLEMENTER_OUTPUT_PATH"),
        implementer_prompt_path=implementer_prompt_path,
        implementer_schema_path=implementer_schema_path,
        open_findings_path=open_findings_path,
        output_path=output_path,
        plan_path=plan_path,
        repo_path=repo_path,
        review_record_path=env.get("WORKFLOW_REVIEW_RECORD_PATH"),
        run_dir=run_dir,
    )


def build_prompt(role: AgentRole, context: AgentContext) -> str:
    """Build the full prompt for the agent."""
    prompt_template_path = (
        context.implementer_prompt_path
        if role == "implementer"
        else context.code_reviewer_prompt_path
    )
    schema_path = (
        context.implementer_schema_path
        if role == "implementer"
        else context.code_review_schema_path
    )

    prompt_template = Path(prompt_template_path).read_text(encoding="utf-8")
    output_schema = Path(schema_path).read_text(encoding="utf-8")
    approved_plan = Path(context.plan_path).read_text(encoding="utf-8")
    finding_ledger = _read_optional_file(context.finding_ledger_path)
    open_findings = _read_optional_file(context.open_findings_path)
    checks = (
        _read_optional_file(context.checks_path) if context.checks_path else None
    )
    latest_implementer_output = (
        _read_optional_file(context.implementer_output_path)
        if context.implementer_output_path
        else None
    )

    sections = [
        prompt_template.strip(),
        "## 承認済み計画書",
        approved_plan.strip(),
        "## Finding Ledger JSON",
        fenced_json(finding_ledger or "[]"),
        "## 未解決 Findings JSON",
        fenced_json(open_findings or "[]"),
    ]

    if role == "reviewer":
        sections.extend([
            "## Implementer 出力 JSON",
            fenced_json(latest_implementer_output or "{}"),
            "## Check 結果 JSON",
            fenced_json(checks or "{}"),
        ])

        if context.review_record_path:
            sections.extend([
                "## One-shot review context",
                "\n".join([
                    "この実行は one-shot `code:review` です。",
                    f"最終レビュー記録 Markdown は control layer が {_normalize_path_for_prompt(context.review_record_path)} に書き込みます。",
                    "レビュー中にその Markdown がまだ存在しないこと自体を finding にしないでください。",
                    "変更内容、計画適合性、checks 結果、JSON 出力の妥当性を基準に verdict を判定してください。",
                ]),
            ])

    sections.extend([
        "## 試行回数",
        str(context.attempt),
        "## 出力 JSON Schema",
        fenced_json(output_schema),
        "## 出力指示",
        "\n".join([
            "上記 JSON Schema に厳密に一致する JSON オブジェクトだけを返してください。",
            "JSON 以外のテキスト・説明・コードブロックの囲みは不要です。JSONのみを出力してください。",
            "JSON のキー名は schema の `properties` に記載されたとおりに保ち、人間向けの Markdown 文字列は日本語で書いてください。",
        ]),
    ])

    return "\n\n".join(sections)


def write_prompt_file(
    role: AgentRole,
    context: AgentContext,
    prompt: str,
) -> str:
    """Write the prompt to a file and return its path."""
    prompt_dir = Path(context.run_dir) / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = str(
        prompt_dir / f"{str(context.attempt).zfill(3)}-{role}.md"
    )
    Path(prompt_path).write_text(prompt + "\n", encoding="utf-8")
    return prompt_path


def run_workflow_agent(provider: WorkflowProvider, role: AgentRole) -> None:
    """Execute the workflow agent — unified entry point for all providers."""
    context = load_context(role)
    prompt = build_prompt(role, context)
    write_prompt_file(role, context, prompt)

    schema_path = (
        context.implementer_schema_path
        if role == "implementer"
        else context.code_review_schema_path
    )

    result = run_structured_prompt(
        cwd=context.repo_path,
        output_path=context.output_path,
        prompt=prompt,
        provider=provider,
        schema_path=schema_path,
    )

    if result.exit_code != 0:
        raise RuntimeError(
            f"{provider.value} {role} command failed with exit code {result.exit_code}:\n"
            + (result.stderr or result.stdout)
        )


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _read_optional_file(file_path: str | None) -> str | None:
    if not file_path:
        return None
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None


def _normalize_path_for_prompt(file_path: str) -> str:
    return str(Path(file_path).resolve()).replace("\\", "/")


@click.command("run")
@click.option(
    "--provider",
    required=True,
    type=click.Choice(["codex", "claude", "gemini"]),
    help="Provider to use.",
)
@click.option(
    "--role",
    required=True,
    type=click.Choice(["implementer", "reviewer"]),
    help="Agent role.",
)
def agent_run_command(provider: str, role: str) -> None:
    """Run a workflow agent with the specified provider and role."""
    run_workflow_agent(
        provider=WorkflowProvider(provider),
        role=role,  # type: ignore[arg-type]
    )
