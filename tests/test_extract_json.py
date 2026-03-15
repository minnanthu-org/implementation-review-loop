"""Tests for JSON extraction — ported from extract-json.test.ts."""

from __future__ import annotations

import pytest

from agent_loop.core.providers.claude import extract_json


def test_returns_raw_json_as_is() -> None:
    text = '{"conclusion":"approve","summaryMd":"OK"}'
    assert extract_json(text) == text


def test_extracts_json_from_code_block_wrapper() -> None:
    json_str = '{"conclusion":"approve","summaryMd":"OK"}'
    text = f"```json\n{json_str}\n```"
    assert extract_json(text) == json_str


def test_extracts_json_preceded_by_text() -> None:
    json_str = '{"conclusion":"approve","summaryMd":"OK"}'
    text = f"Here is the result:\n{json_str}"
    assert extract_json(text) == json_str


def test_extracts_json_followed_by_text() -> None:
    json_str = '{"conclusion":"approve","summaryMd":"OK"}'
    text = f"{json_str}\nDone."
    assert extract_json(text) == json_str


def test_handles_nested_braces_in_json_values() -> None:
    json_str = '{"summaryMd":"code: `{}`","conclusion":"approve"}'
    assert extract_json(json_str) == json_str


def test_handles_escaped_quotes_in_string_values() -> None:
    json_str = '{"summaryMd":"said \\"hello\\"","conclusion":"approve"}'
    assert extract_json(json_str) == json_str


def test_throws_when_no_json_is_present() -> None:
    text = "レビュー完了です。結論は approve です。"
    with pytest.raises(RuntimeError, match="Could not extract valid JSON from Claude output"):
        extract_json(text)


def test_throws_for_empty_input() -> None:
    with pytest.raises(RuntimeError, match="Could not extract valid JSON from Claude output"):
        extract_json("")
