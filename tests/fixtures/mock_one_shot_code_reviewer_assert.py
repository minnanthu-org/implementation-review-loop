#!/usr/bin/env python3
"""Mock one-shot code reviewer with assertions — Python port of mock-one-shot-code-reviewer-assert.mjs."""

import json
import os
import sys


def main() -> None:
    implementer_output_path = os.environ.get("WORKFLOW_IMPLEMENTER_OUTPUT_PATH")
    output_path = os.environ.get("WORKFLOW_CODE_REVIEW_OUTPUT_PATH")
    expected_changed_files = json.loads(
        os.environ.get("EXPECTED_CHANGED_FILES_JSON", "[]")
    )
    expected_checks = json.loads(os.environ.get("EXPECTED_CHECKS_JSON", "[]"))

    if not implementer_output_path:
        print("WORKFLOW_IMPLEMENTER_OUTPUT_PATH is required", file=sys.stderr)
        sys.exit(1)

    if not output_path:
        print("WORKFLOW_CODE_REVIEW_OUTPUT_PATH is required", file=sys.stderr)
        sys.exit(1)

    with open(implementer_output_path, encoding="utf-8") as f:
        implementer_output = json.load(f)

    if json.dumps(implementer_output["changedFiles"]) != json.dumps(
        expected_changed_files
    ):
        raise RuntimeError(
            f"Unexpected changedFiles: {json.dumps(implementer_output['changedFiles'])}"
        )

    if json.dumps(implementer_output["checksRun"]) != json.dumps(expected_checks):
        raise RuntimeError(
            f"Unexpected checksRun: {json.dumps(implementer_output['checksRun'])}"
        )

    payload = {
        "verdict": "approve",
        "summaryMd": "期待した changedFiles と checksRun が reviewer に渡されています。",
        "findings": [],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    main()
