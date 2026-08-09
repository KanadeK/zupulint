# Configuration

Pass a YAML configuration with `zupulint scan INPUT --config zupulint.yml`. Configuration is recursively merged with safe defaults, validated strictly, and rejects unknown keys, invalid ranges, malformed severities, and unsupported locale/version values. The machine-readable contract is the published [`zupulint-config.schema.json`](https://kanadek.github.io/zupulint/schemas/zupulint-config.schema.json).

```yaml
version: 1
locale: zh-CN
rules:
  enabled: true
  disabled: []
  severity:
    ZP602: warning
chronology:
  minimum_parent_age: 12
  maximum_maternal_age: 60
  maximum_paternal_age: 90
  maximum_lifespan: 130
  historical_people: []
generation:
  base_generation: 1
  branch_generation_names:
    main: [守, 浩, 绍, 中, 德, 承, 先, 启, 后, 贤]
  ignore_names: []
privacy:
  redact_living_people: true
  living_person_year_threshold: 110
  expose_exact_birth_date: false
  expose_contact_details: false
report:
  include_info: true
  include_evidence: true
  include_suggestions: true
important_claims_require_sources: false
```

## Rule controls

- `rules.enabled: false` returns a parsed but unscanned result.
- `rules.disabled` lists exact rule IDs to omit.
- `rules.severity` maps exact rule IDs to `error`, `warning`, or `info`.
- `report.include_info: false` suppresses informational results such as default-severity ZP602.

CLI `--fail-on` is independent from configured severity: it controls the process exit threshold after the scan.

## Chronology

Parent-age limits are inclusive policy boundaries used by ZP103. `minimum_parent_age` must be below both maxima. `historical_people` is a list of reviewed IDs exempt only from ZP105 maximum-lifespan findings.

## Generation characters

`base_generation` maps the first configured poem character to an integer generation. Each branch has its own ordered character list. People with a declared branch that is not configured trigger ZP204. `ignore_names` should contain only documented naming exceptions.

## Privacy

The checked-in defaults are deliberately conservative. `--no-redact` changes `redact_living_people` for that CLI run and may itself trigger ZP502 when sensitive living-person data is present. Do not publish an unredacted report by accident.

## Sources

`important_claims_require_sources` is opt-in because early transcriptions are often incomplete. When enabled, ZP603 checks dated/generation person claims and important adoption, succession, or dated relationship claims.
