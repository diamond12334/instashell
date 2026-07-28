"""Standalone entry point for Iron & Ash.

Exists so the game can be started without ``-m`` semantics - by PyInstaller
executables, IDE run buttons, or a plain ``python run_game.py``.
"""
import sys
from pathlib import Path

# When run from a source checkout (not an installed package or frozen exe),
# make sure the package directory is importable regardless of the cwd.
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from iron_and_ash.app import main

if __name__ == "__main__":
    main()
