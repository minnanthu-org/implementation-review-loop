"""Claude CLI integration."""

from __future__ import annotations

import json
import os
from pathlib import Path

from agent_loop.core.process import CommandExecutionResult, run_shell_command, shell_escape

DEFAULT_CLAUDE_EXEC_TIMEOUT_MS = 3_600_000


def build_structured_claude_command(
    *, cwd: str, model: str | None = None, schema_path: str
) -> str:
    """Build a non-interactive Claude command with structured output."""
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    escaped_schema = shell_escape(json.dumps(schema))

    parts = [
        "claude -p",
        # text を使用: json はエンベロープを返すため、--json-schema と組み合わせて
        # スキーマ準拠の raw JSON を得るには text が正しい
        "--output-format text",
        "--input-format text",
        "--permission-mode acceptEdits",
        "--no-session-persistence",
        f"--json-schema {escaped_schema}",
    ]

    if model:
        parts.append(f"--model {shell_escape(model)}")

    return " ".join(parts)


def run_structured_claude_prompt(
    *,
    cwd: str,
    env: dict[str, str] | None = None,
    model: str | None = None,
    output_path: str,
    prompt: str,
    schema_path: str,
    timeout_ms: int | None = None,
) -> CommandExecutionResult:
    """Run a structured Claude prompt and write JSON output to *output_path*."""
    command = build_structured_claude_command(cwd=cwd, model=model, schema_path=schema_path)
    merged_env = {**os.environ, **(env or {})}

    result = run_shell_command(
        command=command,
        cwd=cwd,
        env=merged_env,
        stdin_text=prompt,
        timeout_ms=timeout_ms if timeout_ms is not None else DEFAULT_CLAUDE_EXEC_TIMEOUT_MS,
    )

    if result.exit_code == 0:
        trimmed = result.stdout.strip()

        if not trimmed:
            raise RuntimeError("Claude prompt returned empty output")

        extracted = extract_json(trimmed)
        Path(output_path).write_text(f"{extracted}\n", encoding="utf-8")

    return result


def extract_json(text: str) -> str:
    """Extract a JSON object from *text*, handling code-block wrappers and noise."""
    # 1. Try direct parse
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # 2. Find the first '{' and extract the balanced JSON object.
    #    This handles code-block wrappers and summaryMd fields that contain
    #    triple-backtick code blocks (which break regex-based extraction).
    first_brace = text.find("{")
    if first_brace != -1:
        depth = 0
        in_string = False
        escaped = False
        i = first_brace
        while i < len(text):
            ch = text[i]
            if escaped:
                escaped = False
                i += 1
                continue
            if ch == "\\" and in_string:
                escaped = True
                i += 1
                continue
            if ch == '"':
                in_string = not in_string
                i += 1
                continue
            if in_string:
                i += 1
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[first_brace : i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        # malformed — keep searching for next '{'
                        next_brace = text.find("{", i + 1)
                        if next_brace == -1:
                            break
                        # restart from next brace
                        return extract_json(text[next_brace:])
            i += 1

    raise RuntimeError(
        f"Could not extract valid JSON from Claude output:\n{text[:500]}"
    )


