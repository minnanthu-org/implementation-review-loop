#!/usr/bin/env python3
"""Mock code reviewer agent — Python port of mock-reviewer.mjs."""

import json
import os
import sys


def main() -> None:
    implementer_output_path = os.environ.get("WORKFLOW_IMPLEMENTER_OUTPUT_PATH")
    output_path = os.environ.get("WORKFLOW_CODE_REVIEW_OUTPUT_PATH")

    if not implementer_output_path:
        print("WORKFLOW_IMPLEMENTER_OUTPUT_PATH is required", file=sys.stderr)
        sys.exit(1)

    if not output_path:
        print("WORKFLOW_CODE_REVIEW_OUTPUT_PATH is required", file=sys.stderr)
        sys.exit(1)

    with open(implementer_output_path, encoding="utf-8") as f:
        implementer_output = json.load(f)

    if implementer_output["attempt"] == 1:
        payload = {
            "verdict": "fix",
            "summaryMd": "One finding remains open.",
            "findings": [
                {
                    "id": "F-001",
                    "severity": "high",
                    "status": "open",
                    "summaryMd": "Add a null guard before dereferencing.",
                    "suggestedActionMd": "Handle null input before access.",
                },
            ],
        }
    else:
        payload = {
            "verdict": "approve",
            "summaryMd": "All findings are resolved.",
            "findings": [
                {
                    "id": "F-001",
                    "severity": "high",
                    "status": "closed",
                    "summaryMd": "Null guard is now present.",
                    "suggestedActionMd": "No further action required.",
                },
            ],
        }

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    main()
