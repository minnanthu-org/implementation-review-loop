"""agent-loop plan new — plan file scaffolding, matching new-plan.ts."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import click

from agent_loop.core.repo_config import load_repo_config

DEFAULT_AUTHOR = "Codex"


@dataclass(frozen=True)
class ScaffoldPaths:
    plan_path: str
    review_path: str


def scaffold_plan_files(
    *,
    author: str,
    date: str,
    repo_path: str,
    slug: str,
    title: str,
) -> ScaffoldPaths:
    """Create plan and review files from templates."""
    resolved = str(Path(repo_path).resolve())
    repo_config = load_repo_config(resolved)
    plan_template_path = Path(resolved) / repo_config.plansDir / "TEMPLATE.md"
    review_template_path = Path(resolved) / repo_config.reviewsDir / "TEMPLATE.md"
    yyyymmdd = date.replace("-", "")
    plan_file_name = f"{yyyymmdd}-{slug}.md"
    review_file_name = f"{yyyymmdd}-{slug}-review.md"

    plan_path = str(Path(resolved) / repo_config.plansDir / plan_file_name)
    review_path = str(Path(resolved) / repo_config.reviewsDir / review_file_name)

    plan_template = Path(plan_template_path).read_text(encoding="utf-8")
    review_template = Path(review_template_path).read_text(encoding="utf-8")

    Path(plan_path).parent.mkdir(parents=True, exist_ok=True)
    Path(review_path).parent.mkdir(parents=True, exist_ok=True)

    target_plan_path = (
        str(Path(plan_path).relative_to(resolved)).replace("\\", "/")
    )

    # Write plan — exclusive create (fail if exists)
    with open(plan_path, "x", encoding="utf-8") as f:
        f.write(_render_plan_template(plan_template, title=title, date=date, author=author) + "\n")

    # Write review — exclusive create (fail if exists)
    with open(review_path, "x", encoding="utf-8") as f:
        f.write(
            _render_review_template(review_template, title=title, target_plan_path=target_plan_path)
            + "\n"
        )

    return ScaffoldPaths(plan_path=plan_path, review_path=review_path)


def normalize_slug(value: str | None) -> str | None:
    """Normalize a slug value — lowercase, alphanumeric + hyphens."""
    if not value:
        return None
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = normalized.strip("-")
    return normalized or None


def format_tokyo_date() -> str:
    """Return today's date in Asia/Tokyo as YYYY-MM-DD."""
    try:
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo("Asia/Tokyo"))
    except Exception:
        now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d")


def _render_plan_template(
    template: str,
    *,
    title: str,
    date: str,
    author: str,
) -> str:
    return (
        template.replace("# 実装計画書テンプレート", f"# {title} 実装計画書")
        .replace("作成日: YYYY-MM-DD", f"作成日: {date}")
        .replace("作成者: <name>", f"作成者: {author}")
    )


def _render_review_template(
    template: str,
    *,
    title: str,
    target_plan_path: str,
) -> str:
    return (
        template.replace("# 計画レビュー記録テンプレート", f"# {title} 計画レビュー記録")
        .replace("レビュー日: YYYY-MM-DD", "レビュー日: 未定")
        .replace("レビュー担当: <name>", "レビュー担当: 未定")
        .replace(
            "対象計画書: `docs/implementation-plans/<plan-file>.md`",
            f"対象計画書: `{target_plan_path}`",
        )
    )


@click.command("new")
@click.option("--slug", required=True, help="Plan slug (will be normalized).")
@click.option("--title", default=None, help="Plan title (defaults to slug).")
@click.option("--author", default=DEFAULT_AUTHOR, help="Plan author name.")
@click.option("--date", default=None, help="Date (YYYY-MM-DD, defaults to today in Asia/Tokyo).")
@click.option("--repo", default=".", type=click.Path(exists=False), help="Repository path.")
def new_plan_command(
    slug: str,
    title: str | None,
    author: str,
    date: str | None,
    repo: str,
) -> None:
    """Create new implementation plan and review files from templates."""
    normalized = normalize_slug(slug)
    if not normalized:
        raise click.BadParameter("slug must contain at least one alphanumeric character", param_hint="--slug")

    if date is None:
        date = format_tokyo_date()

    if title is None:
        title = normalized

    created = scaffold_plan_files(
        author=author,
        date=date,
        repo_path=repo,
        slug=normalized,
        title=title,
    )

    click.echo(f"[INFO] Created plan: {created.plan_path}", err=True)
    click.echo(f"[INFO] Created plan review: {created.review_path}", err=True)
    sys.stdout.write(f"{created.plan_path}\n{created.review_path}\n")
