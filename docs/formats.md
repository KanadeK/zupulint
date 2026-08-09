# Input formats

All parsers are bounded by a 20 MiB input limit and return the same `Dataset` model: people, relationships, events, sources, and metadata. Standalone ZIP input is rejected. Because XLSX is an OOXML ZIP container, it is preflighted before `openpyxl` runs: unsafe paths, more than 10,000 members, more than 100 MiB expanded data, and extreme compression ratios are rejected.

## GEDCOM

ZupuLint implements a documented GEDCOM 5.5.1/7 subset with a level-aware tree parser:

- `HEAD`, `TRLR`, `INDI`, `FAM`, and `SOUR` root records;
- `NAME`, `ALIA`, `_AKA`, `SEX`, `BIRT`, `DEAT`, `DATE`, `PLAC`, `NOTE`, and `SOUR` values;
- `HUSB`, `WIFE`, and `CHIL` family pointers;
- `CONT` and `CONC` multiline values;
- UTF-8 with or without BOM, then GB18030 fallback;
- unknown nested tags retained under extension metadata;
- recoverable syntax, missing header/terminator, illegal level jump, and dangling-pointer warnings.

The parser caps input at 500,000 lines and nesting level 100. Unsupported vendor semantics remain as extensions instead of being silently invented.

## CSV

CSV uses the Python standard CSV parser with quoted fields, embedded newlines, a header row, configurable one-character delimiter, and UTF-8/BOM or GB18030 decoding. Duplicate headers are rejected with an explicit error before values can be lost; unknown columns are retained as extensions. CSV and XLSX inputs are capped at 100,000 data rows and 512 columns, while previews consume at most eight rows.

Common canonical columns include `id`/`person_id`, `name`/`primary_name`, `sex`, `birth`, `death`, `living`, `generation`, `generation_name`, `branch`, `places`, `notes`, `sources`, `parents`, `adoptive_parents`, `spouse`, `partner`, `heir_to`, `chu_si_to`, `cheng_si_to`, and `jian_tiao_to`. Multiple references can be separated with comma, semicolon, or vertical bar.

Use a JSON source-to-canonical mapping when headers differ:

```json
{
  "person id": "id",
  "display name": "name",
  "parent ids": "parents"
}
```

```bash
zupulint scan family.csv --delimiter ';' --column-map column-map.json
```

## XLSX

XLSX reads cell values with `openpyxl` in non-formula mode. The first row is the header; blank rows are skipped; Python date/datetime cells are normalized; formula-like strings are imported as inert text. Merged cells produce warnings because their implied structure is ambiguous.

If a workbook has multiple sheets, choose one explicitly:

```bash
zupulint scan family.xlsx --sheet People --column-map column-map.json
```

XLSX uses the same canonical columns and relationship syntax as CSV.

## JSON

JSON is validated into the canonical Pydantic model and accepts top-level `people`, `relationships`, `events`, `sources`, and `metadata`. Known fields are typed; unknown forward-compatible fields are retained. Nesting is capped at 64 levels and traversal at 500,000 values before Pydantic processes extensions. The formal contract is the published [`zupulint-input.schema.json`](https://kanadek.github.io/zupulint/schemas/zupulint-input.schema.json).

Minimal input:

```json
{
  "people": [{"id": "P1", "primary_name": "Synthetic Person"}],
  "relationships": [],
  "events": [],
  "sources": []
}
```

## Dates

Supported normalized forms include `YYYY`, `YYYY-MM`, `YYYY-MM-DD`, GEDCOM day-month-year values, `ABT`/`CAL`/`EST`, `BEF`/`AFT`, `BET ... AND ...`, `FROM ... TO ...`, and numeric year ranges. Precision and qualifier are retained. Traditional or otherwise unsupported text is kept as `raw` with precision `unparsed`, then surfaced by ZP602 rather than discarded.

## Safety boundaries

- File content is never executed.
- XLSX macros and ZIP input are not accepted.
- Formula-like spreadsheet strings remain inert.
- Parser warnings are part of scan evidence.
- A partial GEDCOM can be scanned, but missing records are reported rather than synthesized.
