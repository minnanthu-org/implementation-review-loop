"""Workflow data contracts — Pydantic v2 models."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


# --- Enums ---


class ReviewVerdict(str, Enum):
    APPROVE = "approve"
    FIX = "fix"
    REPLAN = "replan"
    HUMAN = "human"


class PlanReviewConclusion(str, Enum):
    APPROVE = "approve"
    NEEDS_FIX = "needs-fix"
    NEEDS_HUMAN = "needs-human"


class PlanReviewFindingType(str, Enum):
    SCOPE = "scope"
    RISK = "risk"
    MISSING_CHECK = "missing-check"
    AMBIGUITY = "ambiguity"


class PlanReviewFindingSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FindingSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FindingStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class ImplementerResponseType(str, Enum):
    FIXED = "fixed"
    NOT_FIXED = "not-fixed"
    NOT_A_BUG = "not-a-bug"
    NEEDS_REPLAN = "needs-replan"
    NEED_MORE_CONTEXT = "need-more-context"


# --- Shared field annotations ---

NonEmptyStr = Annotated[str, Field(min_length=1)]
PositiveInt = Annotated[int, Field(ge=1)]


# --- Models ---


class ReviewFinding(BaseModel):
    id: NonEmptyStr
    severity: FindingSeverity
    status: FindingStatus
    summaryMd: NonEmptyStr
    suggestedActionMd: NonEmptyStr


class PlanReviewFinding(BaseModel):
    id: NonEmptyStr
    type: PlanReviewFindingType
    severity: PlanReviewFindingSeverity
    contentMd: NonEmptyStr
    suggestedFixMd: NonEmptyStr


class PlanReviewOutput(BaseModel):
    conclusion: PlanReviewConclusion
    summaryMd: NonEmptyStr
    findings: list[PlanReviewFinding]
    impactReviewMd: NonEmptyStr
    checksReviewMd: NonEmptyStr
    humanJudgementMd: NonEmptyStr
    reReviewConditionMd: NonEmptyStr


class CodeReviewOutput(BaseModel):
    verdict: ReviewVerdict
    summaryMd: NonEmptyStr
    findings: list[ReviewFinding]


class ImplementerFindingResponse(BaseModel):
    findingId: NonEmptyStr
    responseType: ImplementerResponseType
    noteMd: NonEmptyStr


class ImplementerOutput(BaseModel):
    attempt: PositiveInt
    summaryMd: NonEmptyStr
    changedFiles: list[NonEmptyStr]
    checksRun: list[NonEmptyStr]
    responses: list[ImplementerFindingResponse]
    replanRequired: bool


class FindingLedgerReviewEvent(BaseModel):
    attempt: PositiveInt
    severity: FindingSeverity
    status: FindingStatus
    summaryMd: NonEmptyStr
    suggestedActionMd: NonEmptyStr
    verdict: ReviewVerdict


class FindingLedgerResponseEvent(BaseModel):
    attempt: PositiveInt
    responseType: ImplementerResponseType
    noteMd: NonEmptyStr


class FindingLedgerEntry(BaseModel):
    id: NonEmptyStr
    firstSeenAttempt: PositiveInt
    lastReviewedAttempt: PositiveInt
    currentSeverity: FindingSeverity
    currentStatus: FindingStatus
    summaryMd: NonEmptyStr
    suggestedActionMd: NonEmptyStr
    reviewHistory: list[FindingLedgerReviewEvent]
    responseHistory: list[FindingLedgerResponseEvent]


# FindingLedger is a list of FindingLedgerEntry (matches z.array(findingLedgerEntrySchema))
FindingLedger = list[FindingLedgerEntry]
