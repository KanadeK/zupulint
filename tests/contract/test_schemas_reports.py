from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import jsonschema
import pytest

from zupulint.config import load_config
from zupulint.parsers import parse_file
from zupulint.reports import render_html, render_json, render_sarif
from zupulint.rules import scan

ROOT = Path(__file__).parents[2]
EXPECTED_RULES = {
    "valid": set(),
    "invalid-structure": {"ZP001", "ZP002", "ZP003", "ZP004", "ZP005", "ZP006", "ZP602"},
    "invalid-chronology": {"ZP101", "ZP102", "ZP103", "ZP104", "ZP105"},
    "invalid-generation": {"ZP201", "ZP202", "ZP203", "ZP204"},
    "invalid-adoption": {"ZP301", "ZP302", "ZP303", "ZP304"},
    "privacy-risk": {"ZP501", "ZP503"},
}


def schema(name: str) -> dict[str, object]:
    return cast(
        dict[str, Any],
        json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8")),
    )


def test_input_config_and_report_schemas_validate_real_artifacts() -> None:
    input_payload = json.loads(
        (ROOT / "examples" / "valid" / "family.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(input_payload, schema("zupulint-input.schema.json"))
    jsonschema.validate(load_config(ROOT / "zupulint.yml"), schema("zupulint-config.schema.json"))
    report_payload = json.loads(
        (ROOT / "examples" / "expected-reports" / "valid.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(report_payload, schema("zupulint-report.schema.json"))


@pytest.mark.parametrize(("name", "expected"), EXPECTED_RULES.items())
def test_expected_reports_have_exact_reproducible_rule_sets(name: str, expected: set[str]) -> None:
    payload = json.loads(
        (ROOT / "examples" / "expected-reports" / f"{name}.json").read_text(encoding="utf-8")
    )
    assert set(payload["summary"]["by_rule"]) == expected
    assert payload["summary"]["issues"] == sum(payload["summary"]["by_rule"].values())


def test_report_contracts_escape_input_and_are_self_contained() -> None:
    source = ROOT / "examples" / "invalid" / "privacy-risk.csv"
    result = scan(parse_file(source), scanned_at="2026-01-01T00:00:00+00:00")
    html = render_html(result, "<script>alert(1)</script>.csv")
    assert "<script>alert(1)</script>.csv" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;.csv" in html
    assert "13800000000" not in html
    assert "Rule statistics" in html and "Configuration summary" in html
    assert "https://" not in html and "http://" not in html

    payload = json.loads(render_json(result))
    jsonschema.validate(payload, schema("zupulint-report.schema.json"))
    sarif = json.loads(render_sarif(result))
    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["tool"]["driver"]["rules"]
    assert all("suggestion" in item["properties"] for item in sarif["runs"][0]["results"])
