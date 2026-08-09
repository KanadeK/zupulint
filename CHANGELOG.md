# Changelog

All notable user-visible changes are documented here. The format follows Keep a Changelog principles and the project uses semantic versioning.

## [0.1.0] - Unreleased

### Added

- Canonical people, relationship, event, source, and genealogy-date models.
- Real GEDCOM, CSV, XLSX, and JSON parsing with bounded previews and recoverable parser warnings.
- Twenty-six deterministic rules across seven rule families.
- Typer CLI, FastAPI REST API, and packaged React/Vite local workbench.
- Offline HTML, JSON, and SARIF 2.1.0 reports.
- Strict YAML configuration and public input/config/report JSON Schemas.
- Synthetic fixtures, expected reports, Python/frontend/property/integration/contract/E2E tests.
- Non-root Docker image, three-platform PyInstaller workflow, SHA-256 manifest, and CycloneDX SBOM.

### Security

- Local-only default binding, request size/type limits, temporary-file cleanup, content-safe reports, conservative living-person redaction, and browser security headers.
