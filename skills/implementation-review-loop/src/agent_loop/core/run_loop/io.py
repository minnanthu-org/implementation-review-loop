"""JSON and text file I/O helpers for the run-loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, TypeAdapter

T = TypeVar("T")


def read_json(file_path: str) -> Any:
    """Read and parse a JSON file."""
    contents = Path(file_path).read_text(encoding="utf-8")
    return json.loads(contents)


def read_optional_json(
    file_path: str,
    model_class: type[T],
    fallback: T | None = None,
) -> T | None:
    """Read JSON, validate with *model_class*, return *fallback* on FileNotFoundError."""
    try:
        raw = read_json(file_path)
    except FileNotFoundError:
        return fallback

    if isinstance(model_class, type) and issubclass(model_class, BaseModel):
        return model_class.model_validate(raw)

    adapter: TypeAdapter[T] = TypeAdapter(model_class)
    return adapter.validate_python(raw)


def read_optional_text(file_path: str) -> str | None:
    """Read a text file, returning ``None`` if the file does not exist."""
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def write_json(file_path: str, value: Any) -> None:
    """Write *value* as pretty-printed JSON (2-space indent, trailing newline)."""
    Path(file_path).write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
