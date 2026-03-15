#!/usr/bin/env python3
"""Mock implementer agent — Python port of mock-implementer.mjs."""

import json
import os
import sys


def main() -> None:
    attempt = int(os.environ["WORKFLOW_ATTEMPT"])
    open_findings_path = os.environ["WORKFLOW_OPEN_FINDINGS_PATH"]
    output_path = os.environ.get("WORKFLOW_IMPLEMENTER_OUTPUT_PATH")

    if not output_path:
        print("WORKFLOW_IMPLEMENTER_OUTPUT_PATH is required", file=sys.stderr)
        sys.exit(1)

    with open(open_findings_path, encoding="utf-8") as f:
        open_findings = json.load(f)

    if attempt == 1:
        payload = {
            "attempt": attempt,
            "summaryMd": "Initial implementation completed.",
            "changedFiles": ["src/example.ts"],
            "checksRun": ["mock-check"],
            "responses": [],
            "replanRequired": False,
        }
    else:
        payload = {
            "attempt": attempt,
            "summaryMd": "Addressed the review finding.",
            "changedFiles": ["src/example.ts", "test/example.test.ts"],
            "checksRun": ["mock-check"],
            "responses": [
                {
                    "findingId": finding["id"],
                    "responseType": "fixed",
                    "noteMd": f"Resolved {finding['id']}.",
                }
                for finding in open_findings
            ],
            "replanRequired": False,
        }

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    main()
