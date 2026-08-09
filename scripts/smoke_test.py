"""Small end-to-end smoke check used by local and release workflows."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from zupulint.api.app import app
from zupulint.parsers import parse_file
from zupulint.reports import render_html, render_json, render_sarif
from zupulint.rules import scan

ROOT = Path(__file__).parents[1]


def main() -> None:
    gedcom = parse_file(ROOT / "examples" / "valid" / "family.ged")
    csv_data = parse_file(ROOT / "examples" / "invalid" / "privacy-risk.csv")
    json_data = parse_file(ROOT / "examples" / "invalid" / "invalid-chronology.json")
    xlsx_data = parse_file(
        ROOT / "examples" / "valid" / "family.xlsx",
        sheet="People",
        column_mapping={
            "person id": "id",
            "display name": "name",
            "birth year": "birth",
            "parent ids": "parents",
            "generation": "generation",
        },
    )
    assert (
        len(gedcom.people),
        len(csv_data.people),
        len(json_data.people),
        len(xlsx_data.people),
    ) == (
        16,
        1,
        6,
        4,
    )
    result = scan(gedcom, scanned_at="2026-01-01T00:00:00+00:00")
    assert result.people_count == 16 and not result.issues
    assert render_html(result).startswith("<!doctype html>")
    assert json.loads(render_json(result))["version"] == "0.1.0"
    assert json.loads(render_sarif(result))["version"] == "2.1.0"
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    root = client.get("/")
    assert root.status_code == 200 and "ZupuLint" in root.text
    packaged_javascript = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "src" / "zupulint" / "web_assets" / "assets").glob("*.js"))
    )
    assert "http://127.0.0.1:8000" not in packaged_javascript
    with TemporaryDirectory(prefix="zupulint-smoke-") as temporary:
        report = Path(temporary) / "report.html"
        report.write_text(render_html(result, "family.ged"), encoding="utf-8")
        assert report.stat().st_size > 1_000
    print(f"smoke ok: {result.people_count} people, {result.relationship_count} relationships")


if __name__ == "__main__":
    main()
