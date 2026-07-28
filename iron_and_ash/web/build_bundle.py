"""Bundle the game package into a zip the browser (Pyodide) can unpack.

Produces ``web/iron_and_ash.zip`` containing the ``iron_and_ash`` package with
its data files. The GitHub Pages workflow runs this before deploying, so the web
build always ships the current code; the zip itself is git-ignored.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "iron_and_ash"
OUT = ROOT / "web" / "iron_and_ash.zip"

# extensions worth shipping to the browser
KEEP = {".py", ".json"}


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_dir():
                continue
            if path.suffix not in KEEP:
                continue
            if "__pycache__" in path.parts:
                continue
            arcname = path.relative_to(ROOT).as_posix()  # e.g. iron_and_ash/app.py
            zf.write(path, arcname)
            count += 1
    print(f"wrote {OUT} ({count} files, {OUT.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    main()
