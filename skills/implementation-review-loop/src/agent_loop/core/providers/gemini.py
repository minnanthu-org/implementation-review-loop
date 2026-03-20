"""Gemini CLI integration."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from agent_loop.core.process import CommandExecutionResult, run_shell_command

DEFAULT_GEMINI_EXEC_TIMEOUT_MS = 420_000


def build_structured_gemini_command(*, model: str | None = None) -> str:
    """Build a Gemini command with JSON output format and yolo mode."""
    parts = [
        "gemini",
        "--output-format json",
        "--yolo",  # 自動承認モード
    ]

    if model:
        parts.append(f"--model {model}")

    return " ".join(parts)


def run_structured_gemini_prompt(
    *,
    cwd: str,
    env: dict[str, str] | None = None,
    model: str | None = None,
    output_path: str,
    prompt: str,
    schema_path: str,
    timeout_ms: int | None = None,
) -> CommandExecutionResult:
    """Run a structured Gemini prompt with schema injection into the prompt text."""
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    prompt_with_schema = "\n".join(
        [
            prompt,
            "",
            "## Output Schema",
            "Return a JSON object that strictly follows this schema:",
            "```json",
            json.dumps(schema, indent=2),
            "```",
            "",
            "IMPORTANT: Output ONLY the JSON object. Do not include any other text or formatting before or after the JSON.",
        ]
    )

    command = build_structured_gemini_command(model=model)
    merged_env = {**os.environ, **(env or {})}

    result = run_shell_command(
        command=command,
        cwd=cwd,
        env=merged_env,
        stdin_text=prompt_with_schema,
        timeout_ms=timeout_ms if timeout_ms is not None else DEFAULT_GEMINI_EXEC_TIMEOUT_MS,
    )

    if result.exit_code == 0:
        try:
            output = json.loads(result.stdout)
            # gemini --output-format json returns { response: "...", stats: {...} }
            model_response = output.get("response")

            if not model_response:
                raise RuntimeError("Gemini output missing 'response' field")

            trimmed = model_response.strip()
            if not trimmed:
                raise RuntimeError("Gemini model returned empty response")

            # Find the JSON block
            json_match = re.search(r"(\{[\s\S]*\})", trimmed)
            json_content = json_match.group(1) if json_match else trimmed

            try:
                # Validate it's JSON before writing
                json.loads(json_content)
                Path(output_path).write_text(
                    f"{json_content}\n", encoding="utf-8"
                )
            except json.JSONDecodeError as parse_error:
                print(
                    "Gemini output contains invalid JSON content:",
                    file=sys.stderr,
                )
                print(json_content, file=sys.stderr)
                raise RuntimeError(
                    f"Gemini output contains invalid JSON content: {parse_error}"
                ) from parse_error
        except RuntimeError:
            raise
        except Exception as error:
            print(f"Failed to process Gemini output: {error}", file=sys.stderr)
            print(
                f"Raw stdout from Gemini CLI: {result.stdout}", file=sys.stderr
            )
            raise RuntimeError(
                f"Failed to process Gemini output: {error}"
            ) from error

    return result
