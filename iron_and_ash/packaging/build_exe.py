"""Build a standalone Iron & Ash executable with PyInstaller.

Usage (from the ``iron_and_ash`` directory, on the OS you want a build for):

    python -m pip install pyinstaller
    python packaging/build_exe.py

The result lands in ``dist/``: ``iron-and-ash.exe`` on Windows, ``iron-and-ash``
on Linux/macOS - a single self-contained file needing no Python install.
PyInstaller cannot cross-compile; build on Windows to get a Windows exe (the
GitHub Actions workflow does this automatically for all three platforms).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    lore_dir = ROOT / "iron_and_ash" / "data" / "lore"
    if not lore_dir.exists():
        print("error: lore data not found; run from the game directory", file=sys.stderr)
        return 1
    # --add-data uses a platform-specific separator; keep the destination path
    # identical to the source layout so world.lore's relative lookup works
    # unchanged inside the frozen bundle.
    sep = ";" if os.name == "nt" else ":"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--console",
        "--name", "iron-and-ash",
        "--add-data", f"{lore_dir}{sep}iron_and_ash/data/lore",
        "--clean",
        "--noconfirm",
        str(ROOT / "run_game.py"),
    ]
    print("+", " ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
