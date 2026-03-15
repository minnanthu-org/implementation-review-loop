#!/usr/bin/env python3
"""Mock plan reviewer — Python port of mock-plan-reviewer.mjs."""

import json
import os
import sys


def main() -> None:
    output_path = os.environ.get("PLAN_REVIEW_OUTPUT_PATH")

    if not output_path:
        print("PLAN_REVIEW_OUTPUT_PATH is required", file=sys.stderr)
        sys.exit(1)

    payload = {
        "conclusion": "approve",
        "summaryMd": "この計画はそのまま実装に進めます。",
        "findings": [],
        "impactReviewMd": "- 変更対象は計画の目的に対して妥当です",
        "checksReviewMd": "- `npm run build`\n- `npm test`",
        "humanJudgementMd": "なし",
        "reReviewConditionMd": "スコープが広がる場合は再レビュー",
    }

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    main()
