"""Shared formatting utilities for CLI commands."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from agent_loop.core.repo_config import WorkflowProvider


def extract_plan_title(plan_contents: str, plan_path: str) -> str:
    """Extract the plan title from the first heading, stripping trailing '実装計画書'."""
    match = re.search(r"^#\s+(.+)$", plan_contents, re.MULTILINE)
    if not match:
        return Path(plan_path).stem
    heading = match.group(1).strip()
    return re.sub(r"\s+実装計画書$", "", heading).strip()


def format_tokyo_date() -> str:
    """Return today's date in Asia/Tokyo as YYYY-MM-DD."""
    try:
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo("Asia/Tokyo"))
    except Exception:
        now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d")


def format_provider_display_name(provider: WorkflowProvider | None) -> str:
    """Return a human-friendly display name for the given provider."""
    if provider == WorkflowProvider.CLAUDE:
        return "Claude"
    if provider == WorkflowProvider.GEMINI:
        return "Gemini"
    if provider == WorkflowProvider.CODEX:
        return "Codex"
    return "Custom Reviewer"


def fenced_json(value: str) -> str:
    """Wrap *value* in a JSON fenced code block."""
    return f"```json\n{value.strip()}\n```"
