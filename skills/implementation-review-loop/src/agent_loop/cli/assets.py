"""Asset path resolution via importlib.resources — matching assets.ts."""

from __future__ import annotations

import importlib.resources
from pathlib import Path


def _assets_dir() -> Path:
    """Return the concrete filesystem path of the ``agent_loop.assets`` package."""
    return Path(str(importlib.resources.files("agent_loop.assets")))


def resolve_asset_path(*segments: str) -> str:
    """Resolve a path relative to the assets directory.

    Equivalent to ``resolveCliAssetPath`` in the TS codebase which resolved
    paths relative to the project root (where schemas/, templates/, prompts/
    lived).  In the Python package these are under ``agent_loop/assets/``.
    """
    return str(_assets_dir().joinpath(*segments))
