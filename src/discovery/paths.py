"""Filesystem locations for a discovery workspace."""

import os
from pathlib import Path


def home() -> Path:
    override = os.environ.get("DISCOVERY_HOME")
    if override:
        return Path(override)
    return Path.cwd() / ".discovery"


def sample_dir() -> Path:
    candidates = [
        Path.cwd() / "data" / "sample",
        Path(__file__).resolve().parents[2] / "data" / "sample",
    ]
    for candidate in candidates:
        if (candidate / "signals.json").exists():
            return candidate
    searched = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"Sample workspace not found. Looked in {searched}")


def inbox_dir() -> Path:
    return Path.cwd() / "data" / "inbox"
