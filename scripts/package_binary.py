"""Package a PyInstaller binary with the files needed by a new user."""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).parents[1]


def main() -> None:
    name = os.environ.get("ZUPULINT_ARTIFACT", "zupulint-platform")
    binary = ROOT / "dist" / ("zupulint.exe" if os.name == "nt" else "zupulint")
    if not binary.exists():
        raise FileNotFoundError(binary)
    staging = ROOT / "dist" / name
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    shutil.copy2(binary, staging / binary.name)
    shutil.copy2(ROOT / "LICENSE", staging / "LICENSE")
    shutil.copy2(ROOT / "README.md", staging / "README.txt")
    shutil.copy2(ROOT / "examples" / "configs" / "default.yml", staging / "zupulint-default.yml")
    shutil.copy2(ROOT / "examples" / "valid" / "family.ged", staging / "family.ged")
    archive = ROOT / "dist" / f"{name}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(staging.iterdir()):
            info = zipfile.ZipInfo(
                f"{name}/{path.name}",
                date_time=(2020, 1, 1, 0, 0, 0),
            )
            info.create_system = 3
            info.external_attr = (
                (0o755 if path == staging / binary.name else 0o644) & 0xFFFF
            ) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, path.read_bytes())
    shutil.rmtree(staging)
    print(archive)


if __name__ == "__main__":
    main()
