#!/usr/bin/env python3
"""Mock one-shot code reviewer — Python port of mock-one-shot-code-reviewer.mjs."""

import json
import os
import sys


def main() -> None:
    output_path = os.environ.get("WORKFLOW_CODE_REVIEW_OUTPUT_PATH")
    review_record_path = os.environ.get("WORKFLOW_REVIEW_RECORD_PATH")

    if not output_path:
        print("WORKFLOW_CODE_REVIEW_OUTPUT_PATH is required", file=sys.stderr)
        sys.exit(1)

    if not review_record_path:
        print("WORKFLOW_REVIEW_RECORD_PATH is required", file=sys.stderr)
        sys.exit(1)

    payload = {
        "verdict": "approve",
        "summaryMd": "計画どおりに実装されており、追加の修正は不要です。",
        "findings": [],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    main()
