"""RunState management."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TypedDict

from pydantic import BaseModel

from agent_loop.core.contracts import ReviewFinding, ReviewVerdict


# --- Enums ---


class RunStatus(str, Enum):
    INITIALIZED = "initialized"
    RUNNING = "running"
    APPROVED = "approved"
    NEEDS_REPLAN = "needs-replan"
    NEEDS_HUMAN = "needs-human"
    FAILED = "failed"


# --- Options ---


@dataclass(frozen=True)
class RunLoopOptions:
    checkCommands: list[str]
    codeReviewSchemaPath: str
    implementerCommand: str
    implementerSchemaPath: str
    planPath: str
    repoPath: str
    reviewerCommand: str
    checksFile: str | None = None
    maxAttempts: int | None = None
    runsDir: str | None = None


@dataclass(frozen=True)
class ResolvedRunLoopOptions:
    checkCommands: list[str]
    checksFilePath: str
    codeReviewSchemaPath: str
    codeReviewerPromptPath: str
    implementerCommand: str
    implementerPromptPath: str
    implementerSchemaPath: str
    maxAttempts: int
    repoPath: str
    reviewerCommand: str
    runsDir: str
    sourcePlanPath: str


# --- State model ---


class RunState(BaseModel):
    runId: str
    status: RunStatus
    repoPath: str
    sourcePlanPath: str
    localPlanPath: str
    maxAttempts: int
    currentAttempt: int
    lastVerdict: ReviewVerdict | None = None
    openFindings: list[ReviewFinding]
    findingLedgerPath: str
    implementerCommand: str
    reviewerCommand: str
    checkCommands: list[str]
    checksFilePath: str
    implementerPromptPath: str
    codeReviewerPromptPath: str
    implementerSchemaPath: str
    codeReviewSchemaPath: str
    createdAt: str
    updatedAt: str


class AttemptTiming(TypedDict):
    attempt: int
    implement: float | None
    check: float | None
    review: float | None


@dataclass(frozen=True)
class RunResult:
    runDir: str
    state: RunState
    timing: list[AttemptTiming] = field(default_factory=list)


# --- State helpers ---


def create_initial_state(
    *,
    checkCommands: list[str],
    checksFilePath: str,
    codeReviewSchemaPath: str,
    codeReviewerPromptPath: str,
    findingLedgerPath: str,
    implementerCommand: str,
    implementerPromptPath: str,
    implementerSchemaPath: str,
    localPlanPath: str,
    maxAttempts: int,
    repoPath: str,
    reviewerCommand: str,
    runId: str,
    sourcePlanPath: str,
) -> RunState:
    """Create the initial ``RunState``."""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return RunState(
        runId=runId,
        status=RunStatus.INITIALIZED,
        repoPath=str(Path(repoPath).resolve()),
        sourcePlanPath=sourcePlanPath,
        localPlanPath=localPlanPath,
        maxAttempts=maxAttempts,
        currentAttempt=0,
        openFindings=[],
        findingLedgerPath=findingLedgerPath,
        implementerCommand=implementerCommand,
        reviewerCommand=reviewerCommand,
        checkCommands=list(checkCommands),
        checksFilePath=checksFilePath,
        implementerPromptPath=implementerPromptPath,
        codeReviewerPromptPath=codeReviewerPromptPath,
        implementerSchemaPath=implementerSchemaPath,
        codeReviewSchemaPath=codeReviewSchemaPath,
        createdAt=now,
        updatedAt=now,
    )


def update_state(
    state: RunState,
    **updates: object,
) -> RunState:
    """Return a new ``RunState`` with *updates* applied and ``updatedAt`` refreshed."""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    data = state.model_dump()
    data.update(updates)
    data["updatedAt"] = now
    return RunState.model_validate(data)


# --- Formatting helpers ---


def build_run_id(source_plan_path: str, now: datetime) -> str:
    """Build a run ID from the plan filename and timestamp."""
    stem = Path(source_plan_path).stem
    plan_base = re.sub(r"[^a-zA-Z0-9]+", "-", stem)
    plan_base = plan_base.strip("-").lower()
    return f"{format_timestamp(now)}-{plan_base or 'plan'}"


def format_timestamp(now: datetime) -> str:
    """Format a datetime as a compact ISO string."""
    ts = now.replace(microsecond=0)
    return ts.isoformat().replace("-", "").replace(":", "").replace("+00:00", "Z")


def format_attempt(attempt: int) -> str:
    """Zero-pad attempt number to 3 digits."""
    return str(attempt).zfill(3)


def map_verdict_to_status(verdict: ReviewVerdict) -> RunStatus:
    """Map a review verdict to a run status."""
    mapping = {
        ReviewVerdict.APPROVE: RunStatus.APPROVED,
        ReviewVerdict.REPLAN: RunStatus.NEEDS_REPLAN,
        ReviewVerdict.HUMAN: RunStatus.NEEDS_HUMAN,
        ReviewVerdict.FIX: RunStatus.RUNNING,
    }
    return mapping[verdict]
