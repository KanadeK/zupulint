# Synthetic examples

Every checked-in fixture is fictional and safe to share. `scripts/generate_examples.py` recreates the XLSX workbook and fixed-time expected reports.

| Fixture | Purpose | Expected rules |
|---|---|---|
| `valid/family.ged` | 16 people, 24 relationships, four generations, dates, sources and generation characters | none |
| `valid/family.xlsx` | Multi-sheet workbook with non-canonical headers for sheet selection and column mapping | none after mapping |
| `invalid/invalid-structure.ged` | Duplicate ID, missing reference, self edge, 3-node ancestry cycle, duplicate spouse, role conflict, parser warning | ZP001–ZP006, ZP602 |
| `invalid/invalid-chronology.json` | Reversed life dates, child older than parent, parent-age boundary, partnership conflict, extreme lifespan | ZP101–ZP105 |
| `invalid/invalid-generation.json` | Parent/child jump, sibling mismatch, wrong/missing generation character, unknown branch poem | ZP201–ZP204 |
| `invalid/invalid-adoption.json` | Biological/successor overlap, unmatched chu-si/cheng-si, inheritance conflict, incomplete jian-tiao | ZP301–ZP304 |
| `invalid/privacy-risk.csv` | Clearly synthetic exact birth, phone, email, national ID, address, DNA and public privacy conflict | ZP501, ZP503 with safe defaults |

Reproduce a report:

```bash
uv run zupulint scan examples/valid/family.ged \
  --format html --output valid.html --fail-on error
uv run zupulint scan examples/invalid/invalid-generation.json \
  --format json --output generation.json --fail-on error
```

The checked-in pairs under `examples/expected-reports/` are used by the release gate. JSON is validated against the report schema, exact rule inventories are compared, and every HTML file is checked as a self-contained document.

To regenerate deterministic artifacts after an intentional rule/output change:

```bash
uv run python scripts/generate_examples.py
uv run python scripts/verify_release.py
git diff -- examples/
```

Review and commit fixture changes together with the rule or renderer change that caused them. Never replace these files with real family data.
