"""Tests for workflow contracts — ported from contracts.test.ts."""

from pydantic import TypeAdapter

from agent_loop.core.contracts import (
    CodeReviewOutput,
    FindingLedger,
    FindingLedgerEntry,
    ImplementerOutput,
    PlanReviewOutput,
)


def test_accepts_valid_implementer_payload() -> None:
    parsed = ImplementerOutput.model_validate(
        {
            "attempt": 1,
            "summaryMd": "Implemented the approved null guard.",
            "changedFiles": ["src/foo.ts", "test/foo.test.ts"],
            "checksRun": ["npm test"],
            "responses": [
                {
                    "findingId": "F-001",
                    "responseType": "fixed",
                    "noteMd": "Added a guard clause.",
                },
            ],
            "replanRequired": False,
        }
    )

    assert len(parsed.responses) == 1


def test_accepts_valid_code_review_payload() -> None:
    parsed = CodeReviewOutput.model_validate(
        {
            "verdict": "fix",
            "summaryMd": "One issue remains open.",
            "findings": [
                {
                    "id": "F-001",
                    "severity": "high",
                    "status": "open",
                    "summaryMd": "Null branch is still missing.",
                    "suggestedActionMd": "Handle null before dereferencing.",
                },
            ],
        }
    )

    assert parsed.verdict.value == "fix"


def test_accepts_valid_plan_review_payload() -> None:
    parsed = PlanReviewOutput.model_validate(
        {
            "conclusion": "approve",
            "summaryMd": "この計画はそのまま実装に進めます。",
            "findings": [],
            "impactReviewMd": "- 変更対象は妥当です",
            "checksReviewMd": "- `npm run build`\n- `npm test`",
            "humanJudgementMd": "なし",
            "reReviewConditionMd": "スコープが広がる場合は再レビュー",
        }
    )

    assert parsed.conclusion.value == "approve"


def test_accepts_valid_finding_ledger_payload() -> None:
    adapter = TypeAdapter(list[FindingLedgerEntry])
    parsed: FindingLedger = adapter.validate_python(
        [
            {
                "id": "F-001",
                "firstSeenAttempt": 1,
                "lastReviewedAttempt": 2,
                "currentSeverity": "high",
                "currentStatus": "closed",
                "summaryMd": "Null guard is now present.",
                "suggestedActionMd": "No further action required.",
                "reviewHistory": [
                    {
                        "attempt": 1,
                        "severity": "high",
                        "status": "open",
                        "summaryMd": "Null guard is missing.",
                        "suggestedActionMd": "Add a null guard.",
                        "verdict": "fix",
                    },
                    {
                        "attempt": 2,
                        "severity": "high",
                        "status": "closed",
                        "summaryMd": "Null guard is now present.",
                        "suggestedActionMd": "No further action required.",
                        "verdict": "approve",
                    },
                ],
                "responseHistory": [
                    {
                        "attempt": 2,
                        "responseType": "fixed",
                        "noteMd": "Added the guard clause.",
                    },
                ],
            },
        ]
    )

    assert len(parsed[0].responseHistory) == 1
