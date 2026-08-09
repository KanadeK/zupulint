# ZupuLint · 谱校 v0.1.0

The first public release of a privacy-first genealogy linter for GEDCOM, CSV, XLSX, and JSON. ZupuLint normalizes each input into one canonical model and runs 26 deterministic checks without sending family data to a third party.

## Included

- Python library and `zupulint` CLI with stable exit codes for CI use.
- Local FastAPI service and packaged React workbench with bounded preview, XLSX sheet selection, CSV mapping, filters, and clear-data controls.
- Structure, chronology, generation and generation-character, succession, possible-duplicate, privacy, and data-quality rule families (`ZP001`–`ZP603`).
- Offline HTML, JSON, and SARIF 2.1.0 reports with evidence, confidence, and repair suggestions.
- Synthetic valid and invalid fixtures, formal input/config/report schemas, and a default configuration.
- Non-root Docker image and standalone Windows, Linux, and macOS command-line archives.

## Install and run

```bash
pipx install ./zupulint-0.1.0-py3-none-any.whl
zupulint sample create
zupulint scan zupulint-sample/valid/family.ged --format html --output report.html
zupulint web
```

Or run the container locally:

```bash
docker build -t zupulint:v0.1.0 .
docker run --rm -p 127.0.0.1:8000:8000 --read-only --tmpfs /tmp --cap-drop ALL zupulint:v0.1.0
```

## Downloads and verification

Release assets include the wheel, source distribution, three standalone binary archives, synthetic examples, default YAML configuration, CycloneDX SBOM, and `SHA256SUMS.txt`.

```bash
sha256sum --check SHA256SUMS.txt
```

The standalone archives contain a binary, license, README, default configuration, and a valid GEDCOM fixture. The binary supports `version`, `sample create`, and the same scan/report commands as the Python package.

## Privacy and limits

Processing is local by default. Uploads to the local web service are capped at 20 MiB, temporary files are deleted after each request, request contents are not logged, living-person redaction is enabled by default, and ZupuLint never auto-merges people or rewrites source files. GEDCOM support intentionally covers the documented 5.5.1/7 subset; generation-character and possible-duplicate findings remain review suggestions rather than automatic corrections.

## Next

Planned work includes broader GEDCOM 7 archival records, guided non-mutating repair plans, and additional regional genealogy conventions. See `ROADMAP.md` for the maintained list.
