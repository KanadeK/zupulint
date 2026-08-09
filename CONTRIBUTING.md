# Contributing to ZupuLint

Thank you for helping make genealogy validation safer and more useful. Contributions must preserve local-first privacy, deterministic results, and non-mutating behavior.

## Before opening an issue

- Remove all real names, dates, addresses, IDs, contact details, medical information, and DNA data.
- Reproduce parser/rule bugs with the smallest fictional fixture possible.
- Include the ZupuLint version, operating system, input format, command, exit code, and sanitized error output.
- Report security or privacy vulnerabilities privately as described in `SECURITY.md`.

## Development

Requirements are Python 3.12+, uv, Node.js 22+, pnpm 11.16, and Docker for the container gate.

```bash
make bootstrap
make verify
```

The README lists every equivalent command for environments without Make.

## Change rules

A rule change must include, in one pull request:

1. a stable `RuleDefinition` and deterministic validator behavior;
2. focused unit/property tests and, when relevant, integration/E2E coverage;
3. the rule-reference definition, logic, example, false-positive note, configuration, and repair guidance;
4. intentionally regenerated synthetic expected reports;
5. Schema changes when the public contract changes.

Never make a rule silently rewrite input, automatically merge people, call a remote service, or depend on unordered traversal/current time without an explicit injected value.

## Fixtures and generated files

Use only fictional data. Run `uv run python scripts/generate_examples.py` after an intentional fixture/report change, inspect the diff, then run `uv run python scripts/verify_release.py`. Do not commit `dist/`, `site/`, coverage output, caches, virtual environments, or real genealogy exports.

## Pull requests

Keep changes scoped, explain the user-visible behavior and privacy impact, and record the exact validation commands run. Do not add `continue-on-error`, broad coverage exclusions, or credentials. By contributing, you agree that your work is licensed under Apache-2.0 and follows `CODE_OF_CONDUCT.md`.
