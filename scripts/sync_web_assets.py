"""Copy the verified Vite bundle into the Python package for ``zupulint web``."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "apps" / "web" / "dist"
TARGET = ROOT / "src" / "zupulint" / "web_assets"


def main() -> None:
    index = SOURCE / "index.html"
    assets = SOURCE / "assets"
    if not index.is_file() or not assets.is_dir():
        raise SystemExit("Vite output is missing; run pnpm --dir apps/web build first")
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(SOURCE, TARGET)
    if not list((TARGET / "assets").glob("*.js")):
        raise SystemExit("Packaged workbench has no JavaScript bundle")
    print(f"synced packaged web assets to {TARGET}")


if __name__ == "__main__":
    main()
