"""Write SHA-256 checksums for all release files except the manifest itself."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def main() -> None:
    directory = Path(sys.argv[1] if len(sys.argv) > 1 else "dist").resolve()
    if not directory.is_dir():
        raise SystemExit(f"release directory does not exist: {directory}")
    artifacts = sorted(
        path for path in directory.iterdir() if path.is_file() and path.name != "SHA256SUMS.txt"
    )
    if not artifacts:
        raise SystemExit("no release files found")
    lines = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in artifacts]
    (directory / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"checksummed {len(artifacts)} release files")


if __name__ == "__main__":
    main()
