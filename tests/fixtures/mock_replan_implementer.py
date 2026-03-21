#!/usr/bin/env python3
"""Mock implementer that always requests replan."""

import json
import os
import sys


def main() -> None:
    attempt = int(os.environ["WORKFLOW_ATTEMPT"])
    output_path = os.environ.get("WORKFLOW_IMPLEMENTER_OUTPUT_PATH")

    if not output_path:
        print("WORKFLOW_IMPLEMENTER_OUTPUT_PATH is required", file=sys.stderr)
        sys.exit(1)

    payload = {
        "attempt": attempt,
        "summaryMd": "Replan is required.",
        "changedFiles": [],
        "checksRun": [],
        "responses": [],
        "replanRequired": True,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    main()
