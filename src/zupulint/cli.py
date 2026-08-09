"""Typer command-line interface."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Annotated

import typer
import uvicorn

from zupulint import __version__
from zupulint.config import load_config
from zupulint.parsers import ParseError, parse_file
from zupulint.reports import render_html, render_json, render_sarif
from zupulint.rules import RULE_BY_ID, RULES, ScanResult, scan

app = typer.Typer(help="Privacy-first genealogy linter.", no_args_is_help=True)
rules_app = typer.Typer(help="Inspect available rules.")
sample_app = typer.Typer(help="Create fictional sample files.")
app.add_typer(rules_app, name="rules")
app.add_typer(sample_app, name="sample")


def _exit_for(result: ScanResult, fail_on: str) -> None:
    rank = {"info": 0, "warning": 1, "error": 2}
    if any(rank[issue.severity] >= rank[fail_on] for issue in result.issues):
        raise typer.Exit(1)


@app.command("scan")
def scan_command(
    source: Annotated[Path, typer.Argument(exists=True, readable=True)],
    config: Annotated[Path | None, typer.Option("--config")] = None,
    format: Annotated[str, typer.Option("--format")] = "text",
    output: Annotated[Path | None, typer.Option("--output")] = None,
    fail_on: Annotated[str, typer.Option("--fail-on")] = "error",
    locale: Annotated[str | None, typer.Option("--locale")] = None,
    no_redact: Annotated[bool, typer.Option("--no-redact")] = False,
    sheet: Annotated[str | None, typer.Option("--sheet")] = None,
    encoding: Annotated[str | None, typer.Option("--encoding")] = None,
    delimiter: Annotated[str, typer.Option("--delimiter")] = ",",
    column_map: Annotated[Path | None, typer.Option("--column-map")] = None,
    quiet: Annotated[bool, typer.Option("--quiet")] = False,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    """Scan GEDCOM, CSV, XLSX, or ZupuLint JSON."""
    if format not in {"text", "html", "json", "sarif"} or fail_on not in {
        "info",
        "warning",
        "error",
    }:
        raise typer.BadParameter(
            "format must be text/html/json/sarif and --fail-on must be info/warning/error"
        )
    try:
        active_config = load_config(config)
        if locale:
            if locale not in {"zh-CN", "en"}:
                raise ValueError("--locale must be zh-CN or en")
            active_config["locale"] = locale
        if no_redact:
            active_config["privacy"]["redact_living_people"] = False
        mapping: dict[str, str] | None = None
        if column_map:
            raw_mapping = json.loads(column_map.read_text(encoding="utf-8"))
            if not isinstance(raw_mapping, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in raw_mapping.items()
            ):
                raise ValueError("--column-map must contain a JSON object of string pairs")
            mapping = raw_mapping
        dataset = parse_file(
            source,
            encoding=encoding,
            sheet=sheet,
            delimiter=delimiter,
            column_mapping=mapping,
        )
        result = scan(
            dataset,
            active_config,
            input_info={
                "name": source.name,
                "format": source.suffix.lower().removeprefix("."),
                "size": source.stat().st_size,
                "sheet": sheet,
            },
        )
    except (OSError, ParseError, ValueError) as exc:
        typer.echo(f"zupulint: {exc}", err=True)
        raise typer.Exit(2) from exc
    if format == "html":
        rendered = render_html(result, source.name)
    elif format == "json":
        rendered = render_json(result)
    elif format == "sarif":
        rendered = render_sarif(result)
    else:
        rendered = (
            "\n".join(
                f"{issue.severity.upper():7} {issue.rule_id} {issue.message}"
                for issue in result.issues
            )
            or "No findings."
        )
        if verbose:
            rendered += "\n" + json.dumps(result.summary, ensure_ascii=False, sort_keys=True)
    if output:
        try:
            output.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            typer.echo(f"zupulint: {exc}", err=True)
            raise typer.Exit(2) from exc
    elif not quiet:
        typer.echo(rendered)
    _exit_for(result, fail_on)


@app.command()
def validate(
    source: Annotated[Path, typer.Argument(exists=True, readable=True)],
    config: Annotated[Path | None, typer.Option("--config")] = None,
    sheet: Annotated[str | None, typer.Option("--sheet")] = None,
    encoding: Annotated[str | None, typer.Option("--encoding")] = None,
    delimiter: Annotated[str, typer.Option("--delimiter")] = ",",
) -> None:
    """Validate a file through its real parser and fail only on errors."""
    try:
        result = scan(
            parse_file(source, sheet=sheet, encoding=encoding, delimiter=delimiter),
            load_config(config),
            input_info={
                "name": source.name,
                "format": source.suffix.lower().removeprefix("."),
                "size": source.stat().st_size,
            },
        )
    except (OSError, ParseError, ValueError) as exc:
        typer.echo(f"zupulint: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(json.dumps(result.summary, ensure_ascii=False, sort_keys=True))
    _exit_for(result, "error")


@rules_app.command("list")
def rules_list() -> None:
    for rule in RULES:
        typer.echo(f"{rule.rule_id}\t{rule.default_severity}\t{rule.title}")


@rules_app.command("describe")
def rules_describe(rule_id: str) -> None:
    rule = RULE_BY_ID.get(rule_id.upper())
    if not rule:
        raise typer.BadParameter("Unknown rule ID")
    typer.echo(json.dumps(rule.__dict__, ensure_ascii=False, indent=2))


@sample_app.command("create")
def sample_create(
    destination: Annotated[Path, typer.Option("--destination")] = Path("zupulint-sample"),
) -> None:
    """Create packaged fictional examples, never personal genealogy data."""
    if destination.exists():
        raise typer.BadParameter(f"Destination already exists: {destination}")
    sample_root = files("zupulint").joinpath("sample_data")
    sample_files = (
        "valid/family.ged",
        "invalid/invalid-structure.ged",
        "configs/default.yml",
    )
    for relative in sample_files:
        parts = PurePosixPath(relative).parts
        target = destination.joinpath(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(sample_root.joinpath(*parts).read_bytes())
    typer.echo(f"Created fictional samples at {destination}")


@app.command("web")
def web(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the local API and packaged React workbench."""
    from zupulint.api.app import app as api_app

    uvicorn.run(api_app, host=host, port=port, reload=False, access_log=False)


@app.command("version")
def version() -> None:
    typer.echo(__version__)
