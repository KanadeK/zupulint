# CLI

## Commands

| Command | Purpose |
|---|---|
| `zupulint scan INPUT` | Parse, normalize, run rules, render a report, and apply a configurable failure threshold |
| `zupulint validate INPUT` | Parse and scan, print a JSON summary, and fail only when an error finding exists |
| `zupulint rules list` | List all 26 IDs, default severities, and titles |
| `zupulint rules describe ID` | Print one rule's structured metadata |
| `zupulint sample create` | Copy or generate fictional sample files into a new directory |
| `zupulint web` | Serve the local API and packaged React workbench |
| `zupulint version` | Print the package version |

## Scan options

```bash
zupulint scan family.ged --config zupulint.yml \
  --format html --output report.html --fail-on warning
zupulint scan family.csv --encoding gb18030 --delimiter ';' \
  --column-map column-map.json --format sarif --output report.sarif
zupulint scan family.xlsx --sheet People --format json --output report.json
```

- `--format`: `text` (default), `html`, `json`, or `sarif`.
- `--output`: write UTF-8 output to a file; otherwise print to stdout unless `--quiet`.
- `--fail-on`: `info`, `warning`, or `error` (default).
- `--config`: strict YAML configuration.
- `--locale`: `zh-CN` or `en` for report metadata.
- `--no-redact`: explicitly disable default living-person redaction for this run.
- `--sheet`: XLSX worksheet.
- `--encoding`: explicit text encoding.
- `--delimiter`: single CSV delimiter character.
- `--column-map`: JSON object mapping source headers to canonical columns.
- `--verbose`: append the structured summary to text output.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Parsing succeeded and no finding met `--fail-on` |
| `1` | Parsing succeeded and at least one finding met the threshold |
| `2` | Input, configuration, mapping, output, or runtime failure |

These stable codes make the CLI suitable for pre-commit hooks and CI. A finding exit (`1`) is distinct from an operational failure (`2`).
