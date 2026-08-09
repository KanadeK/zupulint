from __future__ import annotations

import importlib
import io
import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from typer.testing import CliRunner

from zupulint.api.app import app
from zupulint.cli import app as cli
from zupulint.parsers import parse_file
from zupulint.reports import render_html, render_json
from zupulint.rules import scan

ROOT = Path(__file__).parents[2]
runner = CliRunner()
api_module = importlib.import_module("zupulint.api.app")


def xlsx_bytes(second_sheet: bool = False) -> bytes:
    workbook = Workbook()
    active = workbook.active
    assert active is not None
    active.title = "People"
    active.append(["Person ID", "Display Name"])
    active.append(["P1", "Synthetic"])
    if second_sheet:
        workbook.create_sheet("Notes").append(["Synthetic"])
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def test_gedcom_to_model_rules_and_offline_html() -> None:
    dataset = parse_file(ROOT / "examples" / "invalid" / "invalid-structure.ged")
    result = scan(dataset, scanned_at="2026-01-01T00:00:00+00:00")
    html = render_html(result, "invalid-structure.ged")
    assert result.people_count > 0
    assert {"ZP001", "ZP004", "ZP006"} <= {issue.rule_id for issue in result.issues}
    assert html.startswith("<!doctype html>") and "Biological ancestry cycle" in html


def test_xlsx_column_mapping_to_rules_and_json(tmp_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "People"
    sheet.append(["Identifier", "Display", "Born", "Parent IDs"])
    sheet.append(["P1", "Synthetic Parent", 2000, None])
    sheet.append(["C1", "Synthetic Child", 1990, "P1"])
    source = tmp_path / "mapped.xlsx"
    workbook.save(source)
    dataset = parse_file(
        source,
        sheet="People",
        column_mapping={
            "identifier": "id",
            "display": "name",
            "born": "birth",
            "parent ids": "parents",
        },
    )
    payload = json.loads(render_json(scan(dataset, scanned_at="2026-01-01T00:00:00+00:00")))
    assert payload["summary"]["people"] == 2
    assert "ZP102" in payload["summary"]["by_rule"]


def test_cli_scan_exit_codes_formats_and_quiet(tmp_path: Path) -> None:
    valid = ROOT / "examples" / "valid" / "family.ged"
    invalid = ROOT / "examples" / "invalid" / "invalid-structure.ged"
    assert runner.invoke(cli, ["scan", str(valid)]).exit_code == 0
    assert runner.invoke(cli, ["scan", str(invalid)]).exit_code == 1
    assert runner.invoke(cli, ["scan", str(invalid), "--fail-on", "info", "--quiet"]).exit_code == 1

    output = tmp_path / "report.json"
    result = runner.invoke(
        cli, ["scan", str(valid), "--format", "json", "--output", str(output), "--verbose"]
    )
    assert result.exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8"))["summary"]["people"] == 16

    malformed = tmp_path / "bad.json"
    malformed.write_text("{", encoding="utf-8")
    failure = runner.invoke(cli, ["scan", str(malformed)])
    assert failure.exit_code == 2
    assert "Invalid ZupuLint JSON" in failure.output


def test_cli_validation_rules_version_sample_and_bad_options(tmp_path: Path) -> None:
    valid = ROOT / "examples" / "valid" / "family.ged"
    assert runner.invoke(cli, ["validate", str(valid)]).exit_code == 0
    assert "ZP004" in runner.invoke(cli, ["rules", "list"]).output
    described = runner.invoke(cli, ["rules", "describe", "zp004"])
    assert described.exit_code == 0 and "Ancestry cycle" in described.output
    assert runner.invoke(cli, ["rules", "describe", "bad"]).exit_code != 0
    assert runner.invoke(cli, ["version"]).output.strip() == "0.1.0"

    destination = tmp_path / "samples"
    created = runner.invoke(cli, ["sample", "create", "--destination", str(destination)])
    assert created.exit_code == 0
    sample_valid = destination / "valid" / "family.ged"
    sample_invalid = destination / "invalid" / "invalid-structure.ged"
    assert sample_valid.exists()
    assert sample_invalid.exists()
    assert (destination / "configs" / "default.yml").exists()
    assert runner.invoke(cli, ["scan", str(sample_valid)]).exit_code == 0
    assert runner.invoke(cli, ["scan", str(sample_invalid)]).exit_code == 1
    assert (
        runner.invoke(cli, ["sample", "create", "--destination", str(destination)]).exit_code != 0
    )
    assert runner.invoke(cli, ["scan", str(valid), "--format", "xml"]).exit_code != 0


def test_cli_column_mapping_and_config_override(tmp_path: Path) -> None:
    source = tmp_path / "mapped.csv"
    source.write_text("Identifier;Display\nP1;Synthetic\n", encoding="utf-8")
    mapping = tmp_path / "mapping.json"
    mapping.write_text('{"Identifier":"id","Display":"name"}', encoding="utf-8")
    config = tmp_path / "config.yml"
    config.write_text("version: 1\nrules:\n  enabled: false\n", encoding="utf-8")
    result = runner.invoke(
        cli,
        [
            "scan",
            str(source),
            "--delimiter",
            ";",
            "--column-map",
            str(mapping),
            "--config",
            str(config),
            "--locale",
            "en",
            "--no-redact",
            "--verbose",
        ],
    )
    assert result.exit_code == 0
    assert "No findings" in result.output

    mapping.write_text("[]", encoding="utf-8")
    assert runner.invoke(cli, ["scan", str(source), "--column-map", str(mapping)]).exit_code == 2
    assert runner.invoke(cli, ["scan", str(source), "--locale", "xx"]).exit_code == 2

    missing_parent = tmp_path / "missing" / "report.json"
    output_failure = runner.invoke(
        cli,
        ["scan", str(source), "--format", "json", "--output", str(missing_parent)],
    )
    assert output_failure.exit_code == 2


def test_api_health_rules_headers_and_cors() -> None:
    client = TestClient(app)
    response = client.get("/health", headers={"x-request-id": "request-1"})
    assert response.json() == {"status": "ok", "version": "0.1.0"}
    assert response.headers["x-request-id"] == "request-1"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert client.get("/version").json()["version"] == "0.1.0"
    assert len(client.get("/api/rules").json()) == 26
    assert client.get("/api/rules/ZP004").json()["category"] == "structure"
    assert client.get("/api/rules/NOPE").status_code == 404
    favicon = client.get("/favicon.svg")
    assert favicon.status_code == 200
    assert favicon.headers["content-type"].startswith("image/svg+xml")
    assert favicon.text.startswith("<svg")

    preflight = client.options(
        "/api/scan",
        headers={"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "POST"},
    )
    assert preflight.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_api_preview_scan_validate_and_reports() -> None:
    client = TestClient(app)
    csv_payload = b"Identifier,Display\nP1,Synthetic\n"
    preview = client.post("/api/preview", files={"file": ("family.csv", csv_payload, "text/csv")})
    assert preview.status_code == 200
    assert preview.json()["headers"] == ["Identifier", "Display"]

    mapping = json.dumps({"Identifier": "id", "Display": "name"})
    scan_response = client.post(
        "/api/scan",
        files={
            "file": ("../../family.csv", csv_payload, "text/csv"),
            "config_file": ("config.yml", b"version: 1\n", "application/yaml"),
        },
        data={"column_mapping": mapping},
    )
    assert scan_response.status_code == 200
    assert scan_response.json()["scan"]["input"]["name"] == "family.csv"
    assert scan_response.json()["summary"]["people"] == 1

    validation = client.post(
        "/api/validate",
        files={"file": ("family.csv", csv_payload, "text/csv")},
        data={"column_mapping": mapping},
    )
    assert validation.json()["valid"] is True
    for format_name, media_type in [
        ("html", "text/html"),
        ("json", "application/json"),
        ("sarif", "application/sarif+json"),
    ]:
        report = client.post(
            f"/api/report?format={format_name}",
            files={"file": ("family.csv", csv_payload, "text/csv")},
            data={"column_mapping": mapping},
        )
        assert report.status_code == 200
        assert report.headers["content-type"].startswith(media_type)
        assert "attachment" in report.headers["content-disposition"]


def test_api_xlsx_sheet_selection_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    workbook = xlsx_bytes(second_sheet=True)
    preview = client.post(
        "/api/preview", files={"file": ("family.xlsx", workbook, "application/octet-stream")}
    )
    assert preview.json()["requires_sheet"] is True
    loaded = client.post(
        "/api/preview",
        files={"file": ("family.xlsx", workbook, "application/octet-stream")},
        data={"sheet": "People"},
    )
    assert loaded.json()["rows"][0]["Person ID"] == "P1"

    assert client.post("/api/preview", files={"file": ("x.zip", b"x")}).status_code == 415
    assert (
        client.post(
            "/api/preview",
            files={"file": ("x.xlsx", b"not a workbook", "application/octet-stream")},
        ).status_code
        == 422
    )
    assert client.post("/api/scan", files={"file": ("x.json", b"")}).status_code == 422
    assert (
        client.post(
            "/api/scan",
            files={"file": ("x.json", b'{"people":[],"relationships":[]}')},
            data={"column_mapping": "[]"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/report?format=xml",
            files={"file": ("x.json", b'{"people":[],"relationships":[]}')},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/scan",
            files={
                "file": ("x.json", b'{"people":[],"relationships":[]}'),
                "config_file": ("config.txt", b"version: 1"),
            },
        ).status_code
        == 415
    )

    monkeypatch.setattr(api_module, "MAX_UPLOAD_BYTES", 2)
    assert client.post("/api/scan", files={"file": ("x.json", b"123")}).status_code == 413
    monkeypatch.setattr(api_module, "MAX_UPLOAD_BYTES", 20 * 1024 * 1024)
    monkeypatch.setattr(api_module, "MAX_CONFIG_BYTES", 2)
    assert (
        client.post(
            "/api/scan",
            files={
                "file": ("x.json", b'{"people":[],"relationships":[]}'),
                "config_file": ("x.yml", b"123"),
            },
        ).status_code
        == 413
    )


def test_api_temporary_directory_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = tempfile.TemporaryDirectory

    def temporary_directory(*, prefix: str) -> tempfile.TemporaryDirectory[str]:
        return original(prefix=prefix, dir=tmp_path)

    monkeypatch.setattr(api_module.tempfile, "TemporaryDirectory", temporary_directory)
    response = TestClient(app).post(
        "/api/scan",
        files={"file": ("x.json", b'{"people":[],"relationships":[]}')},
    )
    assert response.status_code == 200
    assert list(tmp_path.iterdir()) == []
