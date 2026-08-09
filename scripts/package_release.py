"""Build Python artifacts, example data, SBOM, and a complete checksum manifest."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).parents[1]
BUILD_ENV = {**os.environ, "PYTHONHASHSEED": "0", "SOURCE_DATE_EPOCH": "1577836800"}


def examples_archive(destination: Path) -> None:
    files = sorted(
        path
        for path in (ROOT / "examples").rglob("*")
        if path.is_file() and "expected-reports" not in path.parts
    )
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = zipfile.ZipInfo(
                str(path.relative_to(ROOT)).replace("\\", "/"),
                date_time=(2020, 1, 1, 0, 0, 0),
            )
            info.create_system = 3
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def normalize_sbom(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("serialNumber", None)
    metadata = payload.get("metadata", {})
    if isinstance(metadata, dict):
        metadata["timestamp"] = "2020-01-01T00:00:00Z"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    dist = ROOT / "dist"
    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir()
    subprocess.run(["uv", "build"], cwd=ROOT, env=BUILD_ENV, check=True)
    (dist / ".gitignore").unlink(missing_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "cyclonedx_py",
            "environment",
            "--output-format",
            "json",
            "--output-file",
            str(dist / "SBOM.json"),
        ],
        cwd=ROOT,
        env=BUILD_ENV,
        check=True,
    )
    normalize_sbom(dist / "SBOM.json")
    shutil.copy(ROOT / "examples" / "configs" / "default.yml", dist / "zupulint-default.yml")
    examples_archive(dist / "zupulint-examples.zip")
    subprocess.run(
        [sys.executable, "scripts/write_checksums.py", "dist"],
        cwd=ROOT,
        check=True,
    )
    print("packaged Python artifacts, examples, SBOM, and checksums")


if __name__ == "__main__":
    main()
