"""Fail on common credential shapes in files destined for the repository."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]
PATTERNS = {
    "GitHub token": re.compile(r"\bgh[opusr]_[A-Za-z0-9]{30,}\b"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "Google OAuth token": re.compile(r"\bya29\.[A-Za-z0-9_-]{20,}\b"),
    "generic bearer token": re.compile(r"(?i)authorization\s*[:=]\s*bearer\s+[A-Za-z0-9._-]{20,}"),
}
BINARY_SUFFIXES = {".xlsx", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".whl", ".gz"}


def candidate_files() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]


def main() -> None:
    paths = candidate_files()
    findings: list[str] = []
    for path in paths:
        if not path.is_file() or path.suffix.lower() in BINARY_SUFFIXES:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{path.relative_to(ROOT)}: {label}")
    if findings:
        raise SystemExit("Potential secrets found:\n" + "\n".join(findings))
    print(f"secret scan passed for {len(paths)} candidate files")


if __name__ == "__main__":
    main()
