"""Finding Ledger management."""

from __future__ import annotations

from agent_loop.core.contracts import (
    CodeReviewOutput,
    FindingLedger,
    FindingLedgerEntry,
    FindingLedgerResponseEvent,
    FindingLedgerReviewEvent,
    ImplementerFindingResponse,
    ReviewFinding,
)


def validate_implementer_responses(
    *,
    open_findings: list[ReviewFinding],
    responses: list[ImplementerFindingResponse],
) -> None:
    """Validate that implementer responded to every open finding exactly once."""
    expected_ids = {f.id for f in open_findings}
    seen_ids: set[str] = set()

    for response in responses:
        if response.findingId not in expected_ids:
            raise RuntimeError(
                f"Implementer responded to unknown finding: {response.findingId}"
            )
        if response.findingId in seen_ids:
            raise RuntimeError(
                f"Implementer returned duplicate response for finding: {response.findingId}"
            )
        seen_ids.add(response.findingId)

    for finding_id in expected_ids:
        if finding_id not in seen_ids:
            raise RuntimeError(
                f"Implementer must respond to every open finding. Missing: {finding_id}"
            )


def validate_review_output(
    *,
    prior_open_findings: list[ReviewFinding],
    review_output: CodeReviewOutput,
) -> None:
    """Validate review output consistency — matches ``validateReviewOutput``."""
    prior_open_ids = {f.id for f in prior_open_findings}
    seen_ids: set[str] = set()

    for finding in review_output.findings:
        if finding.id in seen_ids:
            raise RuntimeError(
                f"Code Reviewer returned duplicate finding: {finding.id}"
            )
        seen_ids.add(finding.id)

    for finding_id in prior_open_ids:
        if finding_id not in seen_ids:
            raise RuntimeError(
                f"Code Reviewer must re-evaluate every open finding. Missing: {finding_id}"
            )

    open_findings = [f for f in review_output.findings if f.status.value == "open"]

    if review_output.verdict.value == "approve" and len(open_findings) > 0:
        raise RuntimeError(
            "Code Reviewer cannot approve while open findings remain"
        )

    if review_output.verdict.value == "fix" and len(open_findings) == 0:
        raise RuntimeError(
            "Code Reviewer must keep at least one finding open on fix"
        )


def apply_implementer_responses(
    *,
    attempt: int,
    ledger: FindingLedger,
    responses: list[ImplementerFindingResponse],
) -> FindingLedger:
    """Append implementer responses to ledger entries — matches ``applyImplementerResponses``."""
    if not responses:
        return ledger

    response_by_id = {r.findingId: r for r in responses}

    result: FindingLedger = []
    for entry in ledger:
        response = response_by_id.get(entry.id)
        if response is None:
            result.append(entry)
            continue

        result.append(
            FindingLedgerEntry(
                id=entry.id,
                firstSeenAttempt=entry.firstSeenAttempt,
                lastReviewedAttempt=entry.lastReviewedAttempt,
                currentSeverity=entry.currentSeverity,
                currentStatus=entry.currentStatus,
                summaryMd=entry.summaryMd,
                suggestedActionMd=entry.suggestedActionMd,
                reviewHistory=list(entry.reviewHistory),
                responseHistory=[
                    *entry.responseHistory,
                    FindingLedgerResponseEvent(
                        attempt=attempt,
                        responseType=response.responseType,
                        noteMd=response.noteMd,
                    ),
                ],
            )
        )

    return result


def apply_review_output(
    *,
    attempt: int,
    ledger: FindingLedger,
    review_output: CodeReviewOutput,
) -> FindingLedger:
    """Merge review findings into ledger — matches ``applyReviewOutput``."""
    entries: dict[str, FindingLedgerEntry] = {e.id: e for e in ledger}

    for finding in review_output.findings:
        review_event = FindingLedgerReviewEvent(
            attempt=attempt,
            severity=finding.severity,
            status=finding.status,
            summaryMd=finding.summaryMd,
            suggestedActionMd=finding.suggestedActionMd,
            verdict=review_output.verdict,
        )

        existing = entries.get(finding.id)

        if existing is None:
            entries[finding.id] = FindingLedgerEntry(
                id=finding.id,
                firstSeenAttempt=attempt,
                lastReviewedAttempt=attempt,
                currentSeverity=finding.severity,
                currentStatus=finding.status,
                summaryMd=finding.summaryMd,
                suggestedActionMd=finding.suggestedActionMd,
                reviewHistory=[review_event],
                responseHistory=[],
            )
            continue

        entries[finding.id] = FindingLedgerEntry(
            id=finding.id,
            firstSeenAttempt=existing.firstSeenAttempt,
            lastReviewedAttempt=attempt,
            currentSeverity=finding.severity,
            currentStatus=finding.status,
            summaryMd=finding.summaryMd,
            suggestedActionMd=finding.suggestedActionMd,
            reviewHistory=[*existing.reviewHistory, review_event],
            responseHistory=list(existing.responseHistory),
        )

    return sorted(entries.values(), key=lambda e: e.id)
