"""Regenerate deterministic synthetic fixtures and their expected reports."""

from __future__ import annotations

import io
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from openpyxl import Workbook

from zupulint.config import load_config
from zupulint.parsers import parse_file
from zupulint.reports import render_html, render_json
from zupulint.rules import scan

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "examples" / "expected-reports"
FIXED_TIME = "2026-01-01T00:00:00+00:00"

FIXTURES = {
    "valid": ROOT / "examples" / "valid" / "family.ged",
    "invalid-structure": ROOT / "examples" / "invalid" / "invalid-structure.ged",
    "invalid-chronology": ROOT / "examples" / "invalid" / "invalid-chronology.json",
    "invalid-generation": ROOT / "examples" / "invalid" / "invalid-generation.json",
    "invalid-adoption": ROOT / "examples" / "invalid" / "invalid-adoption.json",
    "privacy-risk": ROOT / "examples" / "invalid" / "privacy-risk.csv",
}


def _write_deterministic_xlsx(path: Path) -> None:
    workbook = Workbook()
    workbook.properties.created = datetime(2020, 1, 1, tzinfo=UTC)
    workbook.properties.modified = datetime(2020, 1, 1, tzinfo=UTC)
    people = workbook.active
    assert people is not None
    people.title = "People"
    people.append(["Person ID", "Display Name", "Birth Year", "Parent IDs", "Generation"])
    people.append(["X1", "守源", 1900, "", 1])
    people.append(["X2", "浩川", 1925, "X1", 2])
    people.append(["X3", "绍林", 1950, "X2", 3])
    people.append(["X4", "中岳", 1975, "X3", 4])
    notes = workbook.create_sheet("Readme")
    notes.append(["Synthetic fixture only"])
    raw = io.BytesIO()
    workbook.save(raw)
    output = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(raw.getvalue()), "r") as source,
        zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target,
    ):
        for name in sorted(source.namelist()):
            original = source.getinfo(name)
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = original.external_attr
            payload = source.read(name)
            if name == "docProps/core.xml":
                payload = re.sub(
                    rb"(<dcterms:modified\b[^>]*>)[^<]*(</dcterms:modified>)",
                    rb"\g<1>2020-01-01T00:00:00Z\g<2>",
                    payload,
                )
            target.writestr(info, payload)
    path.write_bytes(output.getvalue())


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    _write_deterministic_xlsx(ROOT / "examples" / "valid" / "family.xlsx")
    config = load_config(ROOT / "examples" / "configs" / "default.yml")
    for name, fixture in FIXTURES.items():
        dataset = parse_file(fixture)
        result = scan(
            dataset,
            config,
            input_info={
                "name": fixture.name,
                "format": fixture.suffix.removeprefix("."),
                "size": fixture.stat().st_size,
            },
            scanned_at=FIXED_TIME,
        )
        (TARGET / f"{name}.json").write_text(render_json(result), encoding="utf-8")
        (TARGET / f"{name}.html").write_text(render_html(result, fixture.name), encoding="utf-8")
    print(f"generated {len(FIXTURES)} deterministic report pairs")


if __name__ == "__main__":
    main()
