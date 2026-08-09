# Security policy

## Supported versions

The latest GitHub Release is supported. Pre-release branches and older versions may receive a fix only when the same issue affects the latest release.

## Private reporting

Use the repository's **Security → Report a vulnerability** flow (GitHub Private Vulnerability Reporting). Do not open a public issue for a suspected vulnerability.

Include the affected version, impact, minimal reproduction, and mitigation ideas. Never attach real family-tree data, credentials, addresses, national IDs, medical notes, or DNA data; replace them with synthetic values. The maintainer will acknowledge a usable report, investigate, coordinate a fix/advisory, and credit reporters who request attribution.

## Scope

Relevant reports include parser denial of service, path traversal, temporary-file retention, HTML/script injection, unsafe spreadsheet handling, redaction bypass, unintended network transmission, dependency compromise, or a release-integrity problem.

ZupuLint is designed to run locally, accepts only documented file types, caps uploads, deletes request-scoped temporary files, does not enable access logging in `zupulint web`, escapes report content, runs its container as a non-root user, and publishes checksums plus a CycloneDX SBOM. These controls reduce risk but do not make untrusted data harmless; run the tool with least privilege and keep sensitive reports access-controlled.
