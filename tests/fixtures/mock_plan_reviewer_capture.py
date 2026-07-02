#!/usr/bin/env python3
"""Mock plan reviewer that also captures the prompt received on stdin."""

import json
import os
import sys


def main() -> None:
    output_path = os.environ.get("PLAN_REVIEW_OUTPUT_PATH")
    capture_path = os.environ.get("PROMPT_CAPTURE_PATH")

    if not output_path or not capture_path:
        print(
            "PLAN_REVIEW_OUTPUT_PATH and PROMPT_CAPTURE_PATH are required",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(capture_path, "w", encoding="utf-8") as f:
        f.write(sys.stdin.read())

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
