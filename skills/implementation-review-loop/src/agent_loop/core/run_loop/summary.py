"""Execution summary Markdown generation."""

from __future__ import annotations

import re
from pathlib import Path

from agent_loop.core.contracts import (
    CodeReviewOutput,
    FindingLedgerEntry,
)
from agent_loop.core.run_loop.io import read_optional_json, read_optional_text
from agent_loop.core.run_loop.state import AttemptTiming, RunState, format_attempt


def write_run_summary(
    run_dir: str,
    state: RunState,
    timing: list[AttemptTiming] | None = None,
) -> None:
    """Generate and write ``summary.md``."""
    latest_attempt_path = (
        str(Path(run_dir) / "attempts" / f"{format_attempt(state.currentAttempt)}.md")
        if state.currentAttempt > 0
        else None
    )
    latest_review_path = (
        str(Path(run_dir) / "reviews" / f"{format_attempt(state.currentAttempt)}.json")
        if state.currentAttempt > 0
        else None
    )
    latest_checks_path = (
        str(Path(run_dir) / "checks" / f"{format_attempt(state.currentAttempt)}.json")
        if state.currentAttempt > 0
        else None
    )

    finding_ledger_result = read_optional_json(
        state.findingLedgerPath, list[FindingLedgerEntry], []
    )
    latest_attempt_summary = (
        read_optional_text(latest_attempt_path) if latest_attempt_path else None
    )
    latest_review = (
        read_optional_json(latest_review_path, CodeReviewOutput)
        if latest_review_path
        else None
    )
    latest_checks = (
        _read_optional_checks(latest_checks_path)
        if latest_checks_path
        else None
    )

    finding_ledger: list[FindingLedgerEntry] = finding_ledger_result if finding_ledger_result is not None else []

    open_findings = [e for e in finding_ledger if e.currentStatus.value == "open"]
    closed_findings = [e for e in finding_ledger if e.currentStatus.value == "closed"]

    lines: list[str] = [
        "# 実行サマリー",
        "",
        f"- Run ID: `{state.runId}`",
        f"- 状態: `{state.status.value}`",
        f"- 現在の試行回数: {state.currentAttempt}/{state.maxAttempts}",
        f"- 直近の verdict: `{state.lastVerdict.value if state.lastVerdict else 'n/a'}`",
        f"- 元の計画書: `{state.sourcePlanPath}`",
        f"- ローカルコピー: `{state.localPlanPath}`",
        f"- 未解決 finding 数: {len(open_findings)}",
        f"- 解消済み finding 数: {len(closed_findings)}",
        "",
        "## Checks",
        "",
    ]

    if len(state.checkCommands) == 0:
        lines.append("_check command は設定されていません。_")
        lines.append("")
    else:
        for command in state.checkCommands:
            lines.append(f"- `{command}`")
        lines.append("")

    lines.append("## 最新の Implementer 要約")
    lines.append("")
    lines.append(
        latest_attempt_summary.strip() if latest_attempt_summary else "_まだありません。_"
    )
    lines.append("")

    lines.append("## 最新の Review 要約")
    lines.append("")
    lines.append(
        latest_review.summaryMd.strip()
        if latest_review and latest_review.summaryMd
        else "_まだありません。_"
    )
    lines.append("")

    lines.append("## 最新の Check 結果")
    lines.append("")

    check_commands = latest_checks.get("commands") if latest_checks else None
    if not check_commands or not isinstance(check_commands, list) or len(check_commands) == 0:
        lines.append("_まだありません。_")
        lines.append("")
    else:
        for result in check_commands:
            if not isinstance(result, dict):
                continue
            label = "成功" if result.get("ok") else "失敗"
            lines.append(f"- [{label}] `{result.get('command', '')}`")
        lines.append("")

    lines.append("## 未解決 Findings")
    lines.append("")

    if len(open_findings) == 0:
        lines.append("_なし_")
        lines.append("")
    else:
        for entry in open_findings:
            lines.append(
                f"- `{entry.id}` ({entry.currentSeverity.value}) {single_line(entry.summaryMd)}"
            )
        lines.append("")

    lines.append("## 解消済み Findings")
    lines.append("")

    if len(closed_findings) == 0:
        lines.append("_なし_")
        lines.append("")
    else:
        for entry in closed_findings:
            lines.append(
                f"- `{entry.id}` ({entry.currentSeverity.value}) {single_line(entry.summaryMd)}"
            )
        lines.append("")

    if timing:
        lines.append("## 所要時間")
        lines.append("")
        lines.append("| Attempt | Implement | Check | Review | Total |")
        lines.append("|---------|-----------|-------|--------|-------|")
        for t in timing:
            impl = format_duration(t["implement"])
            chk = format_duration(t["check"])
            rev = format_duration(t["review"])
            parts = [v for v in (t["implement"], t["check"], t["review"]) if v is not None]
            total = format_duration(sum(parts)) if parts else "-"
            lines.append(f"| {t['attempt']} | {impl} | {chk} | {rev} | {total} |")
        # Totals row
        all_impl = [t["implement"] for t in timing if t["implement"] is not None]
        all_chk = [t["check"] for t in timing if t["check"] is not None]
        all_rev = [t["review"] for t in timing if t["review"] is not None]
        total_impl = format_duration(sum(all_impl)) if all_impl else "-"
        total_chk = format_duration(sum(all_chk)) if all_chk else "-"
        total_rev = format_duration(sum(all_rev)) if all_rev else "-"
        all_vals = all_impl + all_chk + all_rev
        grand_total = format_duration(sum(all_vals)) if all_vals else "-"
        lines.append(f"| **Total** | {total_impl} | {total_chk} | {total_rev} | {grand_total} |")
        lines.append("")

    Path(run_dir, "summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def format_duration(seconds: float | None) -> str:
    """Format seconds as ``Xm Ys`` or ``Xs``, or ``-`` for None."""
    if seconds is None:
        return "-"
    total = int(seconds)
    m, s = divmod(total, 60)
    if m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def single_line(value: str) -> str:
    """Collapse whitespace to a single space."""
    return re.sub(r"\s+", " ", value).strip()


def _read_optional_checks(file_path: str) -> dict[str, object] | None:
    """Read checks JSON as a plain dict (avoids circular import of AttemptCheckResults)."""
    import json

    try:
        raw = json.loads(Path(file_path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    if isinstance(raw, dict):
        return raw
    return None
