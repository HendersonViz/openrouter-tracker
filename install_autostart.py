#!/usr/bin/env python3
"""Install a GNOME autostart entry for the OpenRouter tracker."""
from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
AUTOSTART_DIR = Path.home() / ".config" / "autostart"
CONFIG_DIR = Path.home() / ".config" / "openrouter-tracker"
DESKTOP_FILE = AUTOSTART_DIR / "openrouter-tracker.desktop"
ENV_SOURCE = PROJECT_ROOT / ".env"
ENV_TARGET = CONFIG_DIR / "config.env"


def _python_exec() -> Path:
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python3"
    if venv_python.exists():
        return venv_python
    return Path(sys.executable).resolve()


def _desktop_entry(exec_path: Path) -> str:
    return f"""[Desktop Entry]
Type=Application
Version=1.0
Name=OpenRouter Tracker
Comment=Track OpenRouter credit usage in the Ubuntu top bar
Exec={exec_path} {PROJECT_ROOT / "run.py"}
Path={PROJECT_ROOT}
Terminal=false
X-GNOME-Autostart-enabled=true
Categories=Utility;
"""


def main() -> int:
    AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if ENV_SOURCE.exists() and not ENV_TARGET.exists():
        ENV_TARGET.write_text(ENV_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")

    DESKTOP_FILE.write_text(_desktop_entry(_python_exec()), encoding="utf-8")
    print(f"Installed autostart entry: {DESKTOP_FILE}")
    if ENV_TARGET.exists():
        print(f"Config file: {ENV_TARGET}")
    else:
        print(f"Create config file: {ENV_TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
