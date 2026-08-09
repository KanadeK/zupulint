# Privacy and security model

Genealogy can expose living relatives, minors, addresses, identifiers, medical notes, and DNA information. ZupuLint therefore defaults to local, non-mutating analysis and conservative report settings.

## Data flow

- The CLI reads the named local file and writes only an explicitly requested report.
- `zupulint web` binds to `127.0.0.1` by default; the browser uploads only to that local FastAPI process.
- There is no telemetry, cloud service, third-party AI call, advertising SDK, or analytics endpoint.
- Request files live in a unique temporary directory and are removed when parsing/scanning ends, including error paths.
- The server does not enable access logs and application code never logs input content.

## Boundaries

- Input size: 20 MiB; configuration size: 256 KiB.
- XLSX expansion: 100 MiB, 10,000 archive members, safe internal paths, and a bounded compression ratio.
- Tabular shape: 100,000 data rows and 512 columns; JSON shape: 64 nesting levels and 500,000 traversed values.
- Accepted input extensions: `.ged`, `.gedcom`, `.csv`, `.xlsx`, `.json`.
- ZIP archives, macros, and executable content are not accepted.
- Spreadsheet formula-like strings are retained as inert text.
- HTML output auto-escapes values and contains no remote script, font, or stylesheet.
- API responses include `no-store`, a restrictive Content Security Policy, `nosniff`, no-referrer, and a permissions policy.

## Living-person logic and redaction

An explicit `living` value takes precedence. Otherwise a death date means deceased; a parsed birth within `living_person_year_threshold` (default 110 years) is treated as living. Unknown birth/death state is not guessed as living, so curators should set `living` explicitly for uncertain records.

Default configuration keeps living-person redaction on and exact birth/contact exposure off. ZP501 flags sensitive living-person fields, ZP502 warns when output settings are unsafe, and ZP503 treats a public record containing high-sensitivity data as an error.

## Sharing reports

Before sending an HTML/JSON/SARIF report:

1. keep the safe privacy defaults;
2. inspect ZP501–ZP503 findings;
3. confirm the output directory and access controls;
4. avoid attaching the original family file unless recipients need it;
5. delete temporary local reports after use when the device is shared.

ZupuLint reduces accidental exposure but does not replace consent, access control, backup encryption, or applicable privacy-law review.
