#!/usr/bin/env python3
"""Project configuration constants."""
from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path.home() / ".config" / "openrouter-tracker"
ENV_FILES = (
    CONFIG_DIR / "config.env",
    PROJECT_ROOT / ".env",
)


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_quotes(value.strip())
        if key:
            os.environ.setdefault(key, value)


for env_file in ENV_FILES:
    _load_env_file(env_file)


OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai")
DEFAULT_MODEL = os.getenv("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4o")
REFRESH_INTERVAL = int(os.getenv("OPENROUTER_REFRESH_INTERVAL", "300"))  # seconds
