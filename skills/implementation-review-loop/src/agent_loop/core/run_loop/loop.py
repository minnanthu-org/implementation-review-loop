"""Main run-loop."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from pydantic import TypeAdapter

from agent_loop.core.checks import (
    extract_plan_check_commands,
    resolve_configured_check_commands,
    run_checks,
)
from agent_loop.core.contracts import (
    CodeReviewOutput,
    FindingLedgerEntry,
    ImplementerOutput,
)
from agent_loop.core.nested_workflow_guard import (
    assert_no_nested_workflow_invocation,
    build_workflow_command_environment,
)
from agent_loop.core.process import ensure_successful_command, run_shell_command
from agent_loop.core.repo_config import load_compat_loop_repo_config
from agent_loop.core.run_loop.findings import (
    apply_implementer_responses,
    apply_review_output,
    validate_implementer_responses,
    validate_review_output,
)
from agent_loop.core.run_loop.io import read_json, write_json
from agent_loop.core.run_loop.state import (
    AttemptTiming,
    RunResult,
    ResolvedRunLoopOptions,
    RunLoopOptions,
    RunState,
    RunStatus,
    build_run_id,
    create_initial_state,
    format_attempt,
    map_verdict_to_status,
    update_state,
)
from agent_loop.core.run_loop.summary import write_run_summary

DEFAULT_AGENT_COMMAND_TIMEOUT_MS = 1_200_000


def initialize_run(options: RunLoopOptions) -> RunResult:
    """Set up a new run directory and initial state."""
    resolved = resolve_run_loop_options(options)
    plan_contents = Path(resolved.sourcePlanPath).read_text(encoding="utf-8")
    run_id = build_run_id(resolved.sourcePlanPath, datetime.now(timezone.utc))
    run_dir = str(Path(resolved.runsDir) / run_id)

    for sub in ("attempts", "reviews", "responses", "checks"):
        (Path(run_dir) / sub).mkdir(parents=True, exist_ok=True)

    local_plan_path = str(Path(run_dir) / "plan.md")
    finding_ledger_path = str(Path(run_dir) / "finding-ledger.json")
    Path(local_plan_path).write_text(plan_contents, encoding="utf-8")
    write_json(finding_ledger_path, [])

    state = create_initial_state(
        checkCommands=resolved.checkCommands,
        checksFilePath=resolved.checksFilePath,
        codeReviewSchemaPath=resolved.codeReviewSchemaPath,
        codeReviewerPromptPath=resolved.codeReviewerPromptPath,
        implementerCommand=resolved.implementerCommand,
        implementerPromptPath=resolved.implementerPromptPath,
        implementerSchemaPath=resolved.implementerSchemaPath,
        localPlanPath=local_plan_path,
        maxAttempts=resolved.maxAttempts,
        repoPath=resolved.repoPath,
        reviewerCommand=resolved.reviewerCommand,
        runId=run_id,
        findingLedgerPath=finding_ledger_path,
        sourcePlanPath=resolved.sourcePlanPath,
    )

    write_run_snapshot(run_dir, state)

    return RunResult(runDir=run_dir, state=state)


def run_loop(options: RunLoopOptions) -> RunResult:
    """Execute the full implement→check→review loop."""
    initialized = initialize_run(options)
    run_dir = initialized.runDir
    state = update_state(initialized.state, status=RunStatus.RUNNING)
    write_run_snapshot(run_dir, state)

    all_timings: list[AttemptTiming] = []

    for attempt in range(1, state.maxAttempts + 1):
        state = update_state(state, currentAttempt=attempt, status=RunStatus.RUNNING)
        write_run_snapshot(run_dir, state)

        attempt_timing: AttemptTiming = {
            "attempt": attempt,
            "implement": None,
            "check": None,
            "review": None,
        }

        open_findings_path = str(Path(run_dir) / "open-findings.json")
        write_json(
            open_findings_path,
            [f.model_dump() for f in state.openFindings],
        )

        implementer_output_path = str(
            Path(run_dir) / "responses" / f"{format_attempt(attempt)}.json"
        )

        t0 = time.monotonic()
        implementer_result = run_shell_command(
            command=state.implementerCommand,
            cwd=state.repoPath,
            env=build_workflow_environment(
                run_dir=run_dir,
                state=state,
                attempt=attempt,
                open_findings_path=open_findings_path,
                implementer_output_path=implementer_output_path,
            ),
            timeout_ms=DEFAULT_AGENT_COMMAND_TIMEOUT_MS,
        )
        attempt_timing["implement"] = time.monotonic() - t0

        ensure_successful_command("Implementer", implementer_result)

        implementer_output = ImplementerOutput.model_validate(
            read_json(implementer_output_path)
        )

        ledger_adapter: TypeAdapter[list[FindingLedgerEntry]] = TypeAdapter(
            list[FindingLedgerEntry]
        )
        finding_ledger_before_review = ledger_adapter.validate_python(
            read_json(state.findingLedgerPath)
        )

        validate_implementer_responses(
            open_findings=state.openFindings,
            responses=implementer_output.responses,
        )

        ledger_with_responses = apply_implementer_responses(
            attempt=attempt,
            ledger=finding_ledger_before_review,
            responses=implementer_output.responses,
        )
        write_json(
            state.findingLedgerPath,
            [e.model_dump() for e in ledger_with_responses],
        )

        Path(run_dir, "attempts", f"{format_attempt(attempt)}.md").write_text(
            f"{implementer_output.summaryMd}\n", encoding="utf-8"
        )

        if implementer_output.replanRequired:
            state = update_state(
                state,
                lastVerdict="replan",
                openFindings=list(state.openFindings),
                status=RunStatus.NEEDS_REPLAN,
            )
            all_timings.append(attempt_timing)
            write_run_snapshot(run_dir, state, timing=all_timings)
            return RunResult(runDir=run_dir, state=state, timing=all_timings)

        t0 = time.monotonic()
        check_results = run_checks(
            commands=state.checkCommands,
            cwd=state.repoPath,
        )
        attempt_timing["check"] = time.monotonic() - t0

        checks_path = str(
            Path(run_dir) / "checks" / f"{format_attempt(attempt)}.json"
        )
        write_json(checks_path, {
            "allPassed": all(r.ok for r in check_results),
            "attempt": attempt,
            "commands": [
                {
                    "command": r.command,
                    "exitCode": r.exit_code,
                    "ok": r.ok,
                    "stdout": r.stdout,
                    "stderr": r.stderr,
                }
                for r in check_results
            ],
        })

        review_output_path = str(
            Path(run_dir) / "reviews" / f"{format_attempt(attempt)}.json"
        )

        t0 = time.monotonic()
        reviewer_result = run_shell_command(
            command=state.reviewerCommand,
            cwd=state.repoPath,
            env=build_workflow_environment(
                run_dir=run_dir,
                state=state,
                attempt=attempt,
                checks_path=checks_path,
                implementer_output_path=implementer_output_path,
                open_findings_path=open_findings_path,
                review_output_path=review_output_path,
            ),
            timeout_ms=DEFAULT_AGENT_COMMAND_TIMEOUT_MS,
        )
        attempt_timing["review"] = time.monotonic() - t0

        ensure_successful_command("Code Reviewer", reviewer_result)

        review_output = CodeReviewOutput.model_validate(
            read_json(review_output_path)
        )
        validate_review_output(
            prior_open_findings=state.openFindings,
            review_output=review_output,
        )

        next_ledger = apply_review_output(
            attempt=attempt,
            ledger=ledger_with_responses,
            review_output=review_output,
        )
        write_json(
            state.findingLedgerPath,
            [e.model_dump() for e in next_ledger],
        )

        state = update_state(
            state,
            lastVerdict=review_output.verdict,
            openFindings=[
                f
                for f in review_output.findings
                if f.status.value == "open"
            ],
            status=map_verdict_to_status(review_output.verdict),
        )

        all_timings.append(attempt_timing)

        if review_output.verdict.value == "approve":
            write_run_snapshot(run_dir, state, timing=all_timings)
            return RunResult(runDir=run_dir, state=state, timing=all_timings)

        if review_output.verdict.value in ("replan", "human"):
            write_run_snapshot(run_dir, state, timing=all_timings)
            return RunResult(runDir=run_dir, state=state, timing=all_timings)

        write_run_snapshot(run_dir, state)

        if attempt == state.maxAttempts:
            state = update_state(state, status=RunStatus.FAILED)
            write_run_snapshot(run_dir, state, timing=all_timings)
            return RunResult(runDir=run_dir, state=state, timing=all_timings)

    state = update_state(initialized.state, status=RunStatus.FAILED)
    write_run_snapshot(run_dir, state, timing=all_timings)
    return RunResult(runDir=run_dir, state=state, timing=all_timings)


# --- Internal helpers ---


def write_run_snapshot(
    run_dir: str,
    state: RunState,
    timing: list[AttemptTiming] | None = None,
) -> None:
    """Write state.json and summary.md."""
    write_json(str(Path(run_dir) / "state.json"), state.model_dump())

    try:
        write_run_summary(run_dir, state, timing=timing)
    except Exception:
        return


def build_workflow_environment(
    *,
    run_dir: str,
    state: RunState,
    attempt: int,
    open_findings_path: str,
    checks_path: str | None = None,
    implementer_output_path: str | None = None,
    review_output_path: str | None = None,
) -> dict[str, str]:
    """Build the WORKFLOW_* environment for subprocess invocations."""
    env = build_workflow_command_environment("loop:run")
    env.update({
        "WORKFLOW_REPO_PATH": state.repoPath,
        "WORKFLOW_RUN_DIR": run_dir,
        "WORKFLOW_PLAN_PATH": state.localPlanPath,
        "WORKFLOW_ATTEMPT": str(attempt),
        "WORKFLOW_OPEN_FINDINGS_PATH": open_findings_path,
        "WORKFLOW_FINDING_LEDGER_PATH": state.findingLedgerPath,
        "WORKFLOW_IMPLEMENTER_PROMPT_PATH": state.implementerPromptPath,
        "WORKFLOW_CODE_REVIEWER_PROMPT_PATH": state.codeReviewerPromptPath,
        "WORKFLOW_IMPLEMENTER_SCHEMA_PATH": state.implementerSchemaPath,
        "WORKFLOW_CODE_REVIEW_SCHEMA_PATH": state.codeReviewSchemaPath,
    })
    if implementer_output_path is not None:
        env["WORKFLOW_IMPLEMENTER_OUTPUT_PATH"] = implementer_output_path
    if checks_path is not None:
        env["WORKFLOW_CHECKS_PATH"] = checks_path
    if review_output_path is not None:
        env["WORKFLOW_CODE_REVIEW_OUTPUT_PATH"] = review_output_path
    if attempt >= 2:
        prev = format_attempt(attempt - 1)
        env["WORKFLOW_PREV_IMPLEMENTER_OUTPUT_PATH"] = str(
            Path(run_dir) / "responses" / f"{prev}.json"
        )
        env["WORKFLOW_PREV_REVIEW_OUTPUT_PATH"] = str(
            Path(run_dir) / "reviews" / f"{prev}.json"
        )
        env["WORKFLOW_PREV_CHECKS_PATH"] = str(
            Path(run_dir) / "checks" / f"{prev}.json"
        )
    return env


def resolve_run_loop_options(options: RunLoopOptions) -> ResolvedRunLoopOptions:
    """Resolve and validate run-loop options."""
    assert_no_nested_workflow_invocation("loop:run")

    repo_path = str(Path(options.repoPath).resolve())
    repo_config = load_compat_loop_repo_config(repo_path)
    source_plan_path = str(Path(repo_path) / options.planPath)
    checks_file_path = str(
        Path(repo_path) / (options.checksFile or repo_config.checksFile)
    )
    check_commands = resolve_configured_check_commands(
        check_commands=list(options.checkCommands),
        checks_file_path=checks_file_path,
        plan_check_commands=extract_plan_check_commands(source_plan_path),
    )

    return ResolvedRunLoopOptions(
        checkCommands=check_commands,
        checksFilePath=checks_file_path,
        codeReviewSchemaPath=str(Path(options.codeReviewSchemaPath).resolve()),
        codeReviewerPromptPath=str(
            Path(repo_path) / repo_config.prompts.reviewer
        ),
        implementerCommand=options.implementerCommand,
        implementerPromptPath=str(
            Path(repo_path) / repo_config.prompts.implementer
        ),
        implementerSchemaPath=str(Path(options.implementerSchemaPath).resolve()),
        maxAttempts=options.maxAttempts if options.maxAttempts is not None else repo_config.maxAttempts,
        repoPath=repo_path,
        reviewerCommand=options.reviewerCommand,
        runsDir=str(Path(repo_path) / (options.runsDir or repo_config.runDir)),
        sourcePlanPath=source_plan_path,
    )
