# Contributing

Use only fictional or thoroughly sanitized fixtures. A bug report should include the version, platform, input format, command, exit code, sanitized error, and the smallest reproduction. Security/privacy issues belong in GitHub Private Vulnerability Reporting, not a public issue.

```bash
make bootstrap
make verify
```

A rule contribution must update the definition, validator, focused tests, complete rule-reference section, expected synthetic reports, and any affected JSON Schema together. Results must remain deterministic. Do not add automatic source-file edits, automatic person merging, network calls, `continue-on-error`, broad test exclusions, or secrets.

See the repository-level [contributing guide](https://github.com/KanadeK/zupulint/blob/main/CONTRIBUTING.md), [Code of Conduct](https://github.com/KanadeK/zupulint/blob/main/CODE_OF_CONDUCT.md), and [security policy](https://github.com/KanadeK/zupulint/blob/main/SECURITY.md) for the complete process.
