"""Cross-platform smoke test for the PyInstaller executable."""

from __future__ import annotations

import os
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parents[1]


def run(binary: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(binary), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def smoke_web(binary: Path) -> None:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    process = subprocess.Popen(
        [str(binary), "web", "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                _, stderr = process.communicate()
                raise SystemExit(f"binary web exited before startup: {stderr}")
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=1
                ) as response:
                    if response.status == 200:
                        break
            except (OSError, urllib.error.URLError):
                time.sleep(0.2)
        else:
            raise SystemExit("binary web did not become healthy in 30 seconds")
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
            body = response.read().decode("utf-8")
            assert response.status == 200 and "ZupuLint" in body
    finally:
        if process.poll() is None:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            else:
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main() -> None:
    binary = ROOT / "dist" / ("zupulint.exe" if os.name == "nt" else "zupulint")
    if not binary.is_file():
        raise SystemExit(f"binary missing: {binary}")
    assert run(binary, "version").stdout.strip() == "0.1.0"
    with tempfile.TemporaryDirectory(prefix="zupulint-binary-") as temporary:
        sample = Path(temporary) / "sample"
        run(binary, "sample", "create", "--destination", str(sample))
        candidates = list(sample.rglob("family.ged")) or list(sample.rglob("family.json"))
        if not candidates:
            raise SystemExit("sample create did not produce a scan-ready file")
        run(binary, "scan", str(candidates[0]), "--fail-on", "error", "--quiet")
    smoke_web(binary)
    print(f"binary smoke passed: {binary.name}")


if __name__ == "__main__":
    main()
