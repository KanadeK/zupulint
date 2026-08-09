"""Executable entry point used by ``python -m zupulint`` and PyInstaller."""

from zupulint.cli import app


def main() -> None:
    app()


if __name__ == "__main__":
    main()
