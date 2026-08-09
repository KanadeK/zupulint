"""Local-only REST interface shared by the packaged UI and other clients."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from zupulint import __version__
from zupulint.config import load_config
from zupulint.parsers import ParseError, parse_file, preview_data
from zupulint.reports import render_html, render_json, render_sarif
from zupulint.rules import RULE_BY_ID, RULES, ScanResult, scan

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_CONFIG_BYTES = 256 * 1024
WEB_DIR = Path(__file__).resolve().parents[1] / "web_assets"

app = FastAPI(
    title="ZupuLint",
    version=__version__,
    description="Privacy-first local genealogy linting",
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type", "x-request-id"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next: Any) -> Any:
    request_id = request.headers.get("x-request-id") or str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; "
        "img-src 'self' data:; connect-src 'self' http://127.0.0.1:8000 http://localhost:8000"
    )
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/version")
def version() -> dict[str, str]:
    return {"version": __version__}


@app.get("/api/rules")
def rules() -> list[dict[str, Any]]:
    return [rule.__dict__ for rule in RULES]


@app.get("/api/rules/{rule_id}")
def rule(rule_id: str) -> dict[str, Any]:
    if rule_id not in RULE_BY_ID:
        raise HTTPException(404, "Unknown rule ID")
    return RULE_BY_ID[rule_id].__dict__


async def _read_upload(file: UploadFile, limit: int, label: str) -> bytes:
    payload = await file.read(limit + 1)
    if len(payload) > limit:
        raise HTTPException(413, f"{label} exceeds {limit // 1024} KiB limit")
    if not payload:
        raise HTTPException(422, f"{label} is empty")
    return payload


def _mapping(value: str | None) -> dict[str, str] | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(422, f"Invalid column mapping JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in parsed.items()
    ):
        raise HTTPException(422, "Column mapping must be a JSON object of string pairs")
    return parsed


async def _load_config_file(
    config_file: UploadFile | None, temporary: Path
) -> dict[str, Any] | None:
    if not config_file:
        return None
    suffix = Path(config_file.filename or "").suffix.lower()
    if suffix not in {".yml", ".yaml"}:
        raise HTTPException(415, "Configuration must be a .yml or .yaml file")
    payload = await _read_upload(config_file, MAX_CONFIG_BYTES, "Configuration")
    config_path = temporary / "config.yml"
    config_path.write_bytes(payload)
    return load_config(config_path)


async def _scan_upload(
    file: UploadFile,
    config_file: UploadFile | None = None,
    *,
    sheet: str | None = None,
    delimiter: str = ",",
    encoding: str | None = None,
    column_mapping: str | None = None,
) -> tuple[ScanResult, str]:
    safe_name = Path(file.filename or "input").name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in {".ged", ".gedcom", ".csv", ".xlsx", ".json"}:
        raise HTTPException(415, "Supported types: GEDCOM, CSV, XLSX, JSON")
    payload = await _read_upload(file, MAX_UPLOAD_BYTES, "Upload")
    with tempfile.TemporaryDirectory(prefix="zupulint-") as temporary_name:
        temporary = Path(temporary_name)
        path = temporary / f"input{suffix}"
        path.write_bytes(payload)
        try:
            config = await _load_config_file(config_file, temporary)
            dataset = parse_file(
                path,
                encoding=encoding,
                sheet=sheet,
                delimiter=delimiter,
                column_mapping=_mapping(column_mapping),
            )
            result = scan(
                dataset,
                config,
                input_info={
                    "name": safe_name,
                    "format": suffix.removeprefix("."),
                    "size": len(payload),
                    "sheet": sheet,
                },
            )
            return result, safe_name
        except HTTPException:
            raise
        except (ParseError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc


@app.post("/api/preview")
async def api_preview(
    file: UploadFile = File(...),
    sheet: str | None = Form(None),
    delimiter: str = Form(","),
    encoding: str | None = Form(None),
) -> dict[str, Any]:
    safe_name = Path(file.filename or "input").name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in {".ged", ".gedcom", ".csv", ".xlsx", ".json"}:
        raise HTTPException(415, "Supported types: GEDCOM, CSV, XLSX, JSON")
    payload = await _read_upload(file, MAX_UPLOAD_BYTES, "Upload")
    try:
        return preview_data(
            payload, suffix, encoding=encoding, sheet=sheet, delimiter=delimiter
        ) | {"name": safe_name, "size": len(payload)}
    except ParseError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/scan")
async def api_scan(
    file: UploadFile = File(...),
    config_file: UploadFile | None = File(None),
    sheet: str | None = Form(None),
    delimiter: str = Form(","),
    encoding: str | None = Form(None),
    column_mapping: str | None = Form(None),
) -> dict[str, object]:
    result, _ = await _scan_upload(
        file,
        config_file,
        sheet=sheet,
        delimiter=delimiter,
        encoding=encoding,
        column_mapping=column_mapping,
    )
    return result.to_dict()


@app.post("/api/validate")
async def api_validate(
    file: UploadFile = File(...),
    config_file: UploadFile | None = File(None),
    sheet: str | None = Form(None),
    delimiter: str = Form(","),
    encoding: str | None = Form(None),
    column_mapping: str | None = Form(None),
) -> dict[str, object]:
    result, _ = await _scan_upload(
        file,
        config_file,
        sheet=sheet,
        delimiter=delimiter,
        encoding=encoding,
        column_mapping=column_mapping,
    )
    return {
        "valid": not any(issue.severity == "error" for issue in result.issues),
        "summary": result.summary,
        "issues": [issue.to_dict() for issue in result.issues],
    }


@app.post("/api/report")
async def api_report(
    format: str,
    file: UploadFile = File(...),
    config_file: UploadFile | None = File(None),
    sheet: str | None = Form(None),
    delimiter: str = Form(","),
    encoding: str | None = Form(None),
    column_mapping: str | None = Form(None),
) -> PlainTextResponse:
    result, input_name = await _scan_upload(
        file,
        config_file,
        sheet=sheet,
        delimiter=delimiter,
        encoding=encoding,
        column_mapping=column_mapping,
    )
    renderers = {"html": render_html, "json": render_json, "sarif": render_sarif}
    if format not in renderers:
        raise HTTPException(422, "format must be html, json, or sarif")
    output = render_html(result, input_name) if format == "html" else renderers[format](result)
    media_type = {
        "html": "text/html",
        "json": "application/json",
        "sarif": "application/sarif+json",
    }[format]
    response = PlainTextResponse(output, media_type=media_type)
    response.headers["Content-Disposition"] = f'attachment; filename="zupulint-report.{format}"'
    return response


if (WEB_DIR / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def web_index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/favicon.svg", include_in_schema=False)
    def web_favicon() -> FileResponse:
        return FileResponse(WEB_DIR / "favicon.svg", media_type="image/svg+xml")

    @app.get("/{client_path:path}", include_in_schema=False)
    def web_client_route(client_path: str) -> FileResponse:
        if client_path.startswith(("api/", "docs", "redoc", "openapi.json")):
            raise HTTPException(404, "Not found")
        return FileResponse(WEB_DIR / "index.html")
