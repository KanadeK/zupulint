"""Static release gate for schemas, rule inventory, and checked-in fixtures."""

from __future__ import annotations

import importlib
import json
import re
import tomllib
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from zupulint import __version__
from zupulint.config import SUPPORTED_RULE_IDS
from zupulint.parsers import parse_file
from zupulint.rules import RULE_BY_ID, scan

ROOT = Path(__file__).parents[1]

EXPECTED_RULES = {
    "invalid-adoption": {"ZP301", "ZP302", "ZP303", "ZP304"},
    "invalid-chronology": {"ZP101", "ZP102", "ZP103", "ZP104", "ZP105"},
    "invalid-generation": {"ZP201", "ZP202", "ZP203", "ZP204"},
    "invalid-structure": {"ZP001", "ZP002", "ZP003", "ZP004", "ZP005", "ZP006", "ZP602"},
    "privacy-risk": {"ZP501", "ZP503"},
    "valid": set(),
}

ALL_RULES = {
    *(f"ZP00{index}" for index in range(1, 7)),
    *(f"ZP10{index}" for index in range(1, 6)),
    *(f"ZP20{index}" for index in range(1, 5)),
    *(f"ZP30{index}" for index in range(1, 5)),
    "ZP401",
    *(f"ZP50{index}" for index in range(1, 4)),
    *(f"ZP60{index}" for index in range(1, 4)),
}

REQUIRED_DIRECTORIES = {
    ".github/workflows",
    ".github/ISSUE_TEMPLATE",
    "apps/web/public",
    "apps/web/src",
    "apps/web/tests",
    "docs",
    "examples/configs",
    "examples/expected-reports",
    "examples/invalid",
    "examples/valid",
    "schemas",
    "scripts",
    "src/zupulint/api",
    "src/zupulint/config",
    "src/zupulint/models",
    "src/zupulint/normalizers",
    "src/zupulint/parsers",
    "src/zupulint/privacy",
    "src/zupulint/reports",
    "src/zupulint/rules",
    "src/zupulint/sample_data",
    "src/zupulint/web_assets",
    "tests/contract",
    "tests/fixtures",
    "tests/integration",
    "tests/unit",
}

REQUIRED_FILES = {
    ".github/workflows/ci.yml",
    ".github/workflows/pages.yml",
    ".github/workflows/release.yml",
    "CHANGELOG.md",
    "CITATION.cff",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "Dockerfile",
    "LICENSE",
    "Makefile",
    "README.md",
    "README.zh-CN.md",
    "ROADMAP.md",
    "SECURITY.md",
    "docker-compose.yml",
    "mkdocs.yml",
    "pnpm-lock.yaml",
    "pyproject.toml",
    "src/zupulint/sample_data/configs/default.yml",
    "src/zupulint/sample_data/invalid/invalid-structure.ged",
    "src/zupulint/sample_data/valid/family.ged",
    "uv.lock",
    "zupulint.yml",
}

REQUIRED_MAKE_TARGETS = {
    "bootstrap",
    "lint",
    "format-check",
    "typecheck",
    "test",
    "test-frontend",
    "test-e2e",
    "build",
    "package",
    "docs",
    "docker-build",
    "security",
    "schema-check",
    "verify",
}


def require_tokens(content: str, tokens: tuple[str, ...], source: str) -> None:
    missing = [token for token in tokens if token not in content]
    assert not missing, f"{source} is missing required entries: {missing}"


def verify_repository_contract() -> None:
    for relative in sorted(REQUIRED_DIRECTORIES):
        assert (ROOT / relative).is_dir(), f"missing required directory: {relative}"
    for relative in sorted(REQUIRED_FILES):
        assert (ROOT / relative).is_file(), f"missing required file: {relative}"

    for module in (
        "zupulint.api",
        "zupulint.config",
        "zupulint.models",
        "zupulint.normalizers",
        "zupulint.parsers",
        "zupulint.privacy",
        "zupulint.reports",
        "zupulint.rules",
    ):
        importlib.import_module(module)

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    make_targets = set(re.findall(r"^([a-z][a-z0-9-]*):", makefile, re.MULTILINE))
    assert REQUIRED_MAKE_TARGETS <= make_targets
    verify_header = re.search(r"^verify:\s*(.+)$", makefile, re.MULTILINE)
    assert verify_header is not None
    verify_dependencies = set(verify_header.group(1).split())
    assert REQUIRED_MAKE_TARGETS - {"bootstrap", "verify"} <= verify_dependencies
    assert "git diff --check" in makefile

    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    require_tokens(
        ci,
        (
            "push:",
            "pull_request:",
            "workflow_dispatch:",
            "uv lock --check",
            "make bootstrap",
            "make verify",
            "docker build",
            "/health",
        ),
        "ci.yml",
    )
    pages = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    require_tokens(
        pages,
        (
            "uv sync --frozen",
            "actions/configure-pages@",
            "actions/upload-pages-artifact@",
            "actions/deploy-pages@",
            "site/examples/index.html",
        ),
        "pages.yml",
    )
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    require_tokens(
        release,
        (
            'tags: ["v*"]',
            "windows-latest",
            "ubuntu-latest",
            "macos-latest",
            "uv sync --frozen",
            "scripts/smoke_binary.py",
            "scripts/package_release.py",
            "scripts/write_checksums.py",
            "softprops/action-gh-release@",
            "dist/SHA256SUMS.txt",
            "dist/SBOM.json",
        ),
        "release.yml",
    )
    workflows = "\n".join((ci, pages, release))
    for forbidden in ("continue-on-error", "|| true", "git commit", "git push"):
        assert forbidden not in workflows, f"forbidden workflow escape hatch: {forbidden}"

    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    require_tokens(
        dockerfile, ("FROM python:3.12-slim", "USER zupulint", "HEALTHCHECK"), "Dockerfile"
    )
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    require_tokens(
        gitignore,
        (".env", "*.token", "token.json", "credentials.json", "node_modules/", ".venv/"),
        ".gitignore",
    )
    app_source = (ROOT / "apps" / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "dangerouslySetInnerHTML" not in app_source
    for readme_name in ("README.md", "README.zh-CN.md"):
        readme = (ROOT / readme_name).read_text(encoding="utf-8")
        require_tokens(
            readme,
            (
                "https://kanadek.github.io/zupulint/",
                "https://github.com/KanadeK/zupulint/releases/tag/v0.1.0",
                "make verify",
                "uv build",
                "docker build -t zupulint:local .",
            ),
            readme_name,
        )


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    verify_repository_contract()
    assert __version__ == "0.1.0"
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == __version__
    web_package = load_json(ROOT / "apps" / "web" / "package.json")
    assert isinstance(web_package, dict) and web_package["version"] == __version__
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    assert citation["version"] == __version__
    assert set(RULE_BY_ID) == ALL_RULES
    assert SUPPORTED_RULE_IDS == ALL_RULES
    for rule in RULE_BY_ID.values():
        assert rule.message
        assert rule.config_schema
        assert rule.evidence
        assert rule.documentation_url.endswith(f"#{rule.rule_id.lower()}")
    packaged_valid = parse_file(ROOT / "src" / "zupulint" / "sample_data" / "valid" / "family.ged")
    assert len(packaged_valid.people) == 4
    assert len(packaged_valid.relationships) == 3
    assert not scan(packaged_valid, scanned_at="2026-01-01T00:00:00+00:00").issues
    packaged_invalid = parse_file(
        ROOT / "src" / "zupulint" / "sample_data" / "invalid" / "invalid-structure.ged"
    )
    packaged_invalid_rules = {
        issue.rule_id
        for issue in scan(packaged_invalid, scanned_at="2026-01-01T00:00:00+00:00").issues
    }
    assert {"ZP001", "ZP002", "ZP003", "ZP004", "ZP005", "ZP006"} <= (packaged_invalid_rules)
    schemas = ROOT / "schemas"
    validators: dict[str, Draft202012Validator] = {}
    for name in ("zupulint-input", "zupulint-config", "zupulint-report"):
        schema = load_json(schemas / f"{name}.schema.json")
        Draft202012Validator.check_schema(schema)
        validators[name] = Draft202012Validator(schema)

    config_schema = load_json(schemas / "zupulint-config.schema.json")
    assert isinstance(config_schema, dict)
    rule_properties = config_schema["properties"]["rules"]["properties"]
    assert set(rule_properties["disabled"]["items"]["enum"]) == ALL_RULES
    assert set(rule_properties["severity"]["propertyNames"]["enum"]) == ALL_RULES

    rule_documentation = (ROOT / "docs" / "rules.md").read_text(encoding="utf-8")
    documented = list(re.finditer(r"^### (ZP\d{3})\b", rule_documentation, re.MULTILINE))
    assert {match.group(1) for match in documented} == ALL_RULES
    required_fields = (
        "**Definition",
        "**Detection:",
        "**Example:",
        "**Possible false positive:",
        "**Configuration:",
        "**Repair:",
    )
    for index, match in enumerate(documented):
        end = (
            documented[index + 1].start()
            if index + 1 < len(documented)
            else len(rule_documentation)
        )
        section = rule_documentation[match.start() : end]
        assert all(field in section for field in required_fields), match.group(1)
        assert f'<a id="{match.group(1).lower()}"></a>' in rule_documentation

    validators["zupulint-config"].validate(
        yaml.safe_load((ROOT / "examples" / "configs" / "default.yml").read_text(encoding="utf-8"))
    )
    for path in sorted((ROOT / "examples" / "invalid").glob("*.json")):
        validators["zupulint-input"].validate(load_json(path))

    reports = ROOT / "examples" / "expected-reports"
    assert {path.stem for path in reports.glob("*.json")} == set(EXPECTED_RULES)
    assert {path.stem for path in reports.glob("*.html")} == set(EXPECTED_RULES)
    for path in sorted(reports.glob("*.json")):
        payload = load_json(path)
        validators["zupulint-report"].validate(payload)
        assert isinstance(payload, dict)
        assert payload["version"] == "0.1.0"
        actual_rules = {issue["rule_id"] for issue in payload["issues"]}
        assert actual_rules == EXPECTED_RULES[path.stem]
        assert payload["summary"]["issues"] == len(payload["issues"])
        for issue in payload["issues"]:
            assert issue["rule_id"] in RULE_BY_ID
            assert issue["severity"] in {"error", "warning", "info"}
    for path in sorted(reports.glob("*.html")):
        html = path.read_text(encoding="utf-8")
        assert html.startswith("<!doctype html>")
        assert "ZupuLint" in html and "<script src=" not in html
    print(
        "release gate passed: repository contract, 26 rules, "
        "3 schemas, 6 JSON reports, 6 HTML reports"
    )


if __name__ == "__main__":
    main()
