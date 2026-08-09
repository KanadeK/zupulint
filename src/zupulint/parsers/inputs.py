"""Real, bounded input parsers that emit the canonical :class:`Dataset` model."""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from itertools import islice
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import BadZipFile, ZipFile

from openpyxl import load_workbook
from pydantic import ValidationError

from zupulint.models import (
    Dataset,
    Event,
    Person,
    Relationship,
    RelationshipType,
    Source,
)
from zupulint.normalizers import parse_date

SUPPORTED_EXTENSIONS = {".ged", ".gedcom", ".csv", ".xlsx", ".json"}
MAX_INPUT_BYTES = 20 * 1024 * 1024
MAX_GEDCOM_LINES = 500_000
MAX_GEDCOM_LEVEL = 100
MAX_TABULAR_ROWS = 100_000
MAX_TABULAR_COLUMNS = 512
MAX_XLSX_MEMBERS = 10_000
MAX_XLSX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_XLSX_COMPRESSION_RATIO = 500
MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 500_000
PREVIEW_ROWS = 8


class ParseError(ValueError):
    """An input was malformed, unsafe, or unsupported."""


@dataclass
class GedNode:
    level: int
    tag: str
    value: str = ""
    pointer: str | None = None
    line: int = 0
    children: list[GedNode] = field(default_factory=list)

    def values(self, tag: str) -> list[str]:
        return [_node_text(node) for node in self.children if node.tag == tag]

    def child(self, tag: str) -> GedNode | None:
        return next((node for node in self.children if node.tag == tag), None)


GED_LINE = re.compile(r"^(\d+)\s+(?:(@[^@]+@)\s+)?([A-Za-z0-9_]+)(?:\s+(.*))?$")
CANONICAL_COLUMNS = {
    "id",
    "person_id",
    "name",
    "primary_name",
    "surname",
    "given_name",
    "generation_name",
    "courtesy_name",
    "alias",
    "sex",
    "birth",
    "birth_date",
    "death",
    "death_date",
    "living",
    "generation",
    "branch",
    "place",
    "places",
    "notes",
    "phone",
    "email",
    "source",
    "sources",
    "privacy_level",
    "parents",
    "adoptive_parents",
    "step_parents",
    "guardians",
    "spouse",
    "partner",
    "relationship_type",
    "heir_to",
    "posthumous_heir_to",
    "chu_si_to",
    "cheng_si_to",
    "jian_tiao_to",
    "ru_zhui_to",
    "ji_si_to",
    "guo_ji_to",
}


def _decode(data: bytes, encoding: str | None = None) -> str:
    encodings = [encoding] if encoding else ["utf-8-sig", "utf-8", "gb18030"]
    for candidate in encodings:
        if candidate is None:
            continue
        try:
            return data.decode(candidate)
        except (LookupError, UnicodeDecodeError):
            continue
    raise ParseError("Unable to decode input as UTF-8 or GB18030")


def _guard_size(data: bytes) -> None:
    if len(data) > MAX_INPUT_BYTES:
        raise ParseError("Input exceeds the 20 MiB parser limit")


def _guard_xlsx_archive(data: bytes) -> None:
    """Reject oversized or structurally unsafe OOXML archives before openpyxl expands them."""

    _guard_size(data)
    try:
        with ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
    except (BadZipFile, OSError) as exc:
        raise ParseError(f"Invalid XLSX workbook: {exc}") from exc
    if len(members) > MAX_XLSX_MEMBERS:
        raise ParseError(f"XLSX archive exceeds {MAX_XLSX_MEMBERS:,} members")
    unsafe_names = []
    for member in members:
        normalized = member.filename.replace("\\", "/")
        path = PurePosixPath(normalized)
        if path.is_absolute() or ".." in path.parts or (path.parts and ":" in path.parts[0]):
            unsafe_names.append(member.filename)
    if unsafe_names:
        raise ParseError("XLSX archive contains an unsafe internal path")
    total_uncompressed = sum(member.file_size for member in members)
    if total_uncompressed > MAX_XLSX_UNCOMPRESSED_BYTES:
        raise ParseError(
            f"XLSX archive exceeds {MAX_XLSX_UNCOMPRESSED_BYTES // (1024 * 1024)} MiB "
            "after decompression"
        )
    total_compressed = sum(member.compress_size for member in members)
    if (
        total_uncompressed > MAX_INPUT_BYTES
        and total_uncompressed / max(total_compressed, 1) > MAX_XLSX_COMPRESSION_RATIO
    ):
        raise ParseError("XLSX archive compression ratio is unsafe")


def _guard_json_shape(value: object) -> None:
    """Bound nested user data before Pydantic walks arbitrary extension values."""

    stack: list[tuple[object, int]] = [(value, 1)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise ParseError(f"JSON exceeds {MAX_JSON_NODES:,} values")
        if depth > MAX_JSON_DEPTH:
            raise ParseError(f"JSON nesting exceeds {MAX_JSON_DEPTH} levels")
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)


def _node_text(node: GedNode) -> str:
    value = node.value
    for child in node.children:
        if child.tag == "CONT":
            value += "\n" + child.value
        elif child.tag == "CONC":
            value += child.value
    return value


def _serialize_extension(node: GedNode) -> dict[str, Any]:
    return {
        "tag": node.tag,
        "value": node.value,
        "line": node.line,
        "children": [_serialize_extension(child) for child in node.children],
    }


def _gedcom_tree(text: str) -> tuple[list[GedNode], list[str]]:
    roots: list[GedNode] = []
    stack: list[GedNode] = []
    warnings: list[str] = []
    lines = text.splitlines()
    if len(lines) > MAX_GEDCOM_LINES:
        raise ParseError(f"GEDCOM exceeds {MAX_GEDCOM_LINES:,} lines")
    for number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue
        match = GED_LINE.match(raw_line.rstrip("\r"))
        if not match:
            warnings.append(f"line {number}: invalid GEDCOM syntax")
            continue
        level, pointer, tag, value = match.groups()
        numeric_level = int(level)
        if numeric_level > MAX_GEDCOM_LEVEL:
            raise ParseError(f"line {number}: GEDCOM level exceeds {MAX_GEDCOM_LEVEL}")
        node = GedNode(
            numeric_level,
            tag.upper(),
            (value or "").strip(),
            pointer=pointer,
            line=number,
        )
        if pointer and node.tag in {"INDI", "FAM", "SOUR"}:
            node.value = pointer
        while stack and stack[-1].level >= numeric_level:
            stack.pop()
        if numeric_level > 0 and not stack:
            warnings.append(f"line {number}: orphaned level {numeric_level} node")
            roots.append(node)
        elif stack:
            if numeric_level > stack[-1].level + 1:
                warnings.append(f"line {number}: illegal GEDCOM level jump")
            stack[-1].children.append(node)
        else:
            roots.append(node)
        stack.append(node)
    if not any(node.tag == "HEAD" for node in roots):
        warnings.append("missing HEAD record")
    if not roots or roots[-1].tag != "TRLR":
        warnings.append("missing TRLR terminator; file may be incomplete")
    return roots, warnings


def _name_parts(name: str) -> tuple[str, str | None, str | None]:
    clean = " ".join(name.replace("/", " ").split())
    segments = [part for part in clean.split() if part]
    surname_match = re.search(r"/(.*?)/", name)
    surname = surname_match.group(1).strip() if surname_match else None
    given = " ".join(part for part in segments if part != surname) or None
    return clean, surname, given


def _event_value(event: GedNode | None, tag: str) -> str | None:
    child = event.child(tag) if event else None
    return _node_text(child) if child else None


def parse_gedcom(data: bytes, encoding: str | None = None) -> Dataset:
    _guard_size(data)
    roots, warnings = _gedcom_tree(_decode(data, encoding))
    people: list[Person] = []
    events: list[Event] = []
    sources: list[Source] = []
    families: dict[str, GedNode] = {}
    known_ids: set[str] = set()
    family_ids: set[str] = set()

    for node in roots:
        if node.tag == "SOUR":
            sources.append(
                Source(
                    id=node.value,
                    title=next(iter(node.values("TITL")), None),
                    type=next(iter(node.values("AUTH")), None),
                    citation=next(iter(node.values("TEXT")), None),
                    repository=next(iter(node.values("REPO")), None),
                )
            )
        elif node.tag == "FAM":
            families[node.value] = node
            family_ids.add(node.value)

    known_tags = {"NAME", "SEX", "BIRT", "DEAT", "NOTE", "SOUR", "FAMC", "FAMS", "ALIA", "_AKA"}
    for node in roots:
        if node.tag != "INDI":
            continue
        known_ids.add(node.value)
        raw_names = node.values("NAME")
        raw_name = raw_names[0] if raw_names else ""
        primary_name, surname, given = _name_parts(raw_name)
        birth = node.child("BIRT")
        death = node.child("DEAT")
        aliases = [
            _name_parts(value)[0]
            for value in [*raw_names[1:], *node.values("ALIA"), *node.values("_AKA")]
            if value
        ]
        notes = node.values("NOTE")
        extensions = {
            "gedcom": [
                _serialize_extension(child)
                for child in node.children
                if child.tag not in known_tags
            ]
        }
        person = Person(
            id=node.value,
            names=[name for name in [primary_name, *aliases] if name],
            primary_name=primary_name or None,
            surname=surname,
            given_name=given,
            alias=aliases,
            sex=(node.values("SEX") or [""])[0] or None,
            birth=parse_date(_event_value(birth, "DATE")),
            death=parse_date(_event_value(death, "DATE")),
            living=False if death else None,
            places=[
                place
                for place in (_event_value(birth, "PLAC"), _event_value(death, "PLAC"))
                if place
            ],
            notes=notes,
            sources=node.values("SOUR"),
            extensions=extensions,
        )
        people.append(person)
        for event_type, event_node in (("birth", birth), ("death", death)):
            if event_node:
                events.append(
                    Event(
                        id=f"{person.id}:{event_type}",
                        person_id=person.id,
                        type=event_type,
                        date=parse_date(_event_value(event_node, "DATE")),
                        place=_event_value(event_node, "PLAC"),
                        description="\n".join(event_node.values("NOTE")) or None,
                        sources=event_node.values("SOUR"),
                    )
                )
        for family_pointer in [*node.values("FAMC"), *node.values("FAMS")]:
            if family_pointer not in family_ids:
                warnings.append(
                    f"line {node.line}: individual {node.value} references missing family {family_pointer}"
                )

    relationships: list[Relationship] = []
    for family_id, family in families.items():
        parents = family.values("HUSB") + family.values("WIFE")
        children = family.values("CHIL")
        marriage = family.child("MARR")
        start = parse_date(_event_value(marriage, "DATE"))
        marriage_sources = marriage.values("SOUR") if marriage else []
        marriage_notes = marriage.values("NOTE") if marriage else []
        for left_index, left in enumerate(parents):
            for right in parents[left_index + 1 :]:
                relationships.append(
                    Relationship(
                        id=f"{family_id}:spouse:{left}:{right}",
                        type=RelationshipType.SPOUSE,
                        from_person_id=left,
                        to_person_id=right,
                        start_date=start,
                        sources=marriage_sources,
                        notes=marriage_notes,
                    )
                )
        for parent in parents:
            for child in children:
                relationships.append(
                    Relationship(
                        id=f"{family_id}:parent:{parent}:{child}",
                        type=RelationshipType.BIOLOGICAL_PARENT,
                        from_person_id=parent,
                        to_person_id=child,
                        sources=family.values("SOUR"),
                    )
                )
    for relationship in relationships:
        missing = {
            identifier
            for identifier in (relationship.from_person_id, relationship.to_person_id)
            if identifier not in known_ids
        }
        if missing:
            warnings.append(
                f"missing GEDCOM pointer(s) {', '.join(sorted(missing))} in {relationship.id}"
            )
    return Dataset(
        people=people,
        relationships=relationships,
        events=events,
        sources=sources,
        metadata={
            "input_format": "gedcom",
            "parse_warnings": warnings,
            "root_records": len(roots),
        },
    )


def _split_refs(value: Any) -> list[str]:
    return [item.strip() for item in re.split(r"[;,|]", str(value or "")) if item.strip()]


def _safe_cell(value: Any, warnings: list[str], location: str) -> Any:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        warnings.append(f"{location}: formula-like value imported as inert text")
        return "'" + value
    return value


def _mapped_row(row: dict[str, Any], column_mapping: dict[str, str] | None) -> dict[str, Any]:
    mapping = {
        key.strip().lower(): value.strip().lower() for key, value in (column_mapping or {}).items()
    }
    return {
        mapping.get(str(key).strip().lower(), str(key).strip().lower()): value
        for key, value in row.items()
        if key is not None and mapping.get(str(key).strip().lower(), str(key).strip().lower())
    }


def _append_relationships(
    relations: list[Relationship], person_id: str, normalized: dict[str, Any]
) -> None:
    relation_columns = {
        "parents": RelationshipType.BIOLOGICAL_PARENT,
        "adoptive_parents": RelationshipType.ADOPTIVE_PARENT,
        "step_parents": RelationshipType.STEP_PARENT,
        "guardians": RelationshipType.GUARDIAN,
    }
    for column, relation_type in relation_columns.items():
        for parent in _split_refs(normalized.get(column)):
            relations.append(
                Relationship(
                    id=f"table:{relation_type.value}:{parent}:{person_id}",
                    type=relation_type,
                    from_person_id=parent,
                    to_person_id=person_id,
                )
            )
    peer_columns = {
        "spouse": RelationshipType.SPOUSE,
        "partner": RelationshipType.PARTNER,
    }
    for column, relation_type in peer_columns.items():
        for peer in _split_refs(normalized.get(column)):
            relations.append(
                Relationship(
                    id=f"table:{relation_type.value}:{person_id}:{peer}",
                    type=relation_type,
                    from_person_id=person_id,
                    to_person_id=peer,
                )
            )
    target_columns = {
        "heir_to": RelationshipType.HEIR,
        "posthumous_heir_to": RelationshipType.POSTHUMOUS_HEIR,
        "chu_si_to": RelationshipType.CHU_SI,
        "cheng_si_to": RelationshipType.CHENG_SI,
        "jian_tiao_to": RelationshipType.JIAN_TIAO,
        "ru_zhui_to": RelationshipType.RU_ZHUI,
        "ji_si_to": RelationshipType.JI_SI,
        "guo_ji_to": RelationshipType.GUO_JI,
    }
    for column, relation_type in target_columns.items():
        for target in _split_refs(normalized.get(column)):
            relations.append(
                Relationship(
                    id=f"table:{relation_type.value}:{person_id}:{target}",
                    type=relation_type,
                    from_person_id=person_id,
                    to_person_id=target,
                )
            )
    if normalized.get("relationship_type") and normalized.get("heir_to"):
        requested = str(normalized["relationship_type"]).strip().lower()
        try:
            requested_type = RelationshipType(requested)
        except ValueError:
            return
        for relation in relations:
            if relation.from_person_id == person_id and relation.type == RelationshipType.HEIR:
                relation.type = requested_type


def _tabular_dataset(
    rows: list[dict[str, Any]],
    *,
    headers: list[str],
    input_format: str,
    warnings: list[str] | None = None,
    column_mapping: dict[str, str] | None = None,
) -> Dataset:
    people: list[Person] = []
    relations: list[Relationship] = []
    parse_warnings = list(warnings or [])
    for index, row in enumerate(rows, start=2):
        normalized = _mapped_row(row, column_mapping)
        person_id = str(normalized.get("id") or normalized.get("person_id") or "").strip()
        name = str(normalized.get("name") or normalized.get("primary_name") or "").strip()
        notes = _split_refs(normalized.get("notes"))
        if normalized.get("phone"):
            notes.append(f"phone: {normalized['phone']}")
        if normalized.get("email"):
            notes.append(f"email: {normalized['email']}")
        aliases = _split_refs(normalized.get("alias"))
        generation_raw = normalized.get("generation")
        generation = int(str(generation_raw)) if str(generation_raw or "").isdigit() else None
        if generation_raw not in (None, "") and generation is None:
            parse_warnings.append(f"row {index}: generation is not an integer")
        person = Person(
            id=person_id,
            names=[item for item in [name, *aliases] if item],
            primary_name=name or None,
            surname=str(normalized.get("surname") or "") or None,
            given_name=str(normalized.get("given_name") or "") or None,
            generation_name=str(normalized.get("generation_name") or "") or None,
            courtesy_name=str(normalized.get("courtesy_name") or "") or None,
            alias=aliases,
            sex=str(normalized.get("sex") or "") or None,
            birth=parse_date(normalized.get("birth") or normalized.get("birth_date")),
            death=parse_date(normalized.get("death") or normalized.get("death_date")),
            living=str(normalized.get("living", "")).lower() in {"true", "yes", "1", "是"}
            if normalized.get("living") not in (None, "")
            else None,
            generation=generation,
            branch=str(normalized.get("branch") or "") or None,
            places=_split_refs(normalized.get("place") or normalized.get("places")),
            notes=notes,
            sources=_split_refs(normalized.get("source") or normalized.get("sources")),
            privacy_level=str(normalized.get("privacy_level") or "private"),
            extensions={
                "_source_row": index,
                **{
                    key: value
                    for key, value in normalized.items()
                    if key not in CANONICAL_COLUMNS and value not in (None, "")
                },
            },
        )
        people.append(person)
        _append_relationships(relations, person_id, normalized)
    return Dataset(
        people=people,
        relationships=relations,
        metadata={
            "input_format": input_format,
            "row_count": len(rows),
            "headers": headers,
            "parse_warnings": parse_warnings,
        },
    )


def _validate_headers(headers: list[str], kind: str) -> None:
    if not headers or not any(headers):
        raise ParseError(f"{kind} requires a first-row header")
    normalized = [header.strip().casefold() for header in headers]
    duplicates = sorted({header for header in normalized if normalized.count(header) > 1})
    if duplicates:
        raise ParseError(f"{kind} contains duplicate column names: {', '.join(duplicates)}")
    if len(headers) > MAX_TABULAR_COLUMNS:
        raise ParseError(f"{kind} exceeds {MAX_TABULAR_COLUMNS} columns")


def parse_csv(
    data: bytes,
    encoding: str | None = None,
    delimiter: str = ",",
    column_mapping: dict[str, str] | None = None,
) -> Dataset:
    _guard_size(data)
    if len(delimiter) != 1:
        raise ParseError("CSV delimiter must be exactly one character")
    text = _decode(data, encoding)
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter)
    headers = [str(item or "").strip() for item in (reader.fieldnames or [])]
    _validate_headers(headers, "CSV")
    rows = list(islice(reader, MAX_TABULAR_ROWS + 1))
    if len(rows) > MAX_TABULAR_ROWS:
        raise ParseError(f"CSV exceeds {MAX_TABULAR_ROWS:,} data rows")
    return _tabular_dataset(
        rows,
        headers=headers,
        input_format="csv",
        column_mapping=column_mapping,
    )


def _xlsx_rows(
    data: bytes, sheet: str | None
) -> tuple[list[str], list[dict[str, Any]], list[str], list[str]]:
    _guard_xlsx_archive(data)
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=False, data_only=False)
    except Exception as exc:
        raise ParseError(f"Invalid XLSX workbook: {exc}") from exc
    if sheet and sheet not in workbook.sheetnames:
        raise ParseError(f"Worksheet not found: {sheet}")
    if not sheet and len(workbook.sheetnames) > 1:
        raise ParseError(
            "Workbook has multiple worksheets; select one of: " + ", ".join(workbook.sheetnames)
        )
    worksheet = workbook[sheet or workbook.sheetnames[0]]
    if worksheet.max_row - 1 > MAX_TABULAR_ROWS:
        raise ParseError(f"XLSX exceeds {MAX_TABULAR_ROWS:,} data rows")
    if worksheet.max_column > MAX_TABULAR_COLUMNS:
        raise ParseError(f"XLSX exceeds {MAX_TABULAR_COLUMNS} columns")
    header = next(worksheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
    headers = [str(cell).strip() if cell is not None else "" for cell in (header or [])]
    _validate_headers(headers, "XLSX")
    warnings: list[str] = []
    if worksheet.merged_cells.ranges:
        warnings.append(
            "merged cells present: "
            + ", ".join(str(item) for item in sorted(worksheet.merged_cells.ranges))
        )
    rows: list[dict[str, Any]] = []
    for row_number, row in enumerate(worksheet.iter_rows(min_row=2, values_only=True), start=2):
        if not any(value is not None and value != "" for value in row):
            continue
        safe_values = [
            _safe_cell(value, warnings, f"{worksheet.title}!{row_number}:{index + 1}")
            for index, value in enumerate(row)
        ]
        rows.append(dict(zip(headers, safe_values, strict=True)))
    return headers, rows, warnings, workbook.sheetnames


def parse_xlsx(
    data: bytes,
    sheet: str | None = None,
    column_mapping: dict[str, str] | None = None,
) -> Dataset:
    headers, rows, warnings, sheets = _xlsx_rows(data, sheet)
    result = _tabular_dataset(
        rows,
        headers=headers,
        input_format="xlsx",
        warnings=warnings,
        column_mapping=column_mapping,
    )
    result.metadata["sheet"] = sheet or sheets[0]
    result.metadata["sheets"] = sheets
    return result


def parse_json(data: bytes) -> Dataset:
    _guard_size(data)
    try:
        raw = json.loads(data.decode("utf-8-sig"))
        if not isinstance(raw, dict):
            raise ParseError("Invalid ZupuLint JSON: top level must be an object")
        _guard_json_shape(raw)
        dataset = Dataset.model_validate(raw)
        dataset.metadata.setdefault("input_format", "json")
        return dataset
    except ParseError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValidationError) as exc:
        raise ParseError(f"Invalid ZupuLint JSON: {exc}") from exc


def preview_data(
    data: bytes,
    suffix: str,
    *,
    encoding: str | None = None,
    sheet: str | None = None,
    delimiter: str = ",",
) -> dict[str, Any]:
    """Return a bounded, local-only import preview used by the web workbench."""

    suffix = suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ParseError(f"Unsupported file type: {suffix or '(none)'}")
    _guard_size(data)
    if suffix == ".csv":
        if len(delimiter) != 1:
            raise ParseError("CSV delimiter must be exactly one character")
        reader = csv.DictReader(
            io.StringIO(_decode(data, encoding), newline=""), delimiter=delimiter
        )
        headers = [str(item or "").strip() for item in (reader.fieldnames or [])]
        _validate_headers(headers, "CSV")
        rows = [
            {key: "" if value is None else str(value)[:200] for key, value in row.items()}
            for row in islice(reader, PREVIEW_ROWS)
        ]
        sheets: list[str] = []
        warnings: list[str] = []
    elif suffix == ".xlsx":
        _guard_xlsx_archive(data)
        if not sheet:
            try:
                workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=False)
            except Exception as exc:
                raise ParseError(f"Invalid XLSX workbook: {exc}") from exc
            if len(workbook.sheetnames) > 1:
                return {
                    "format": "xlsx",
                    "sheets": workbook.sheetnames,
                    "requires_sheet": True,
                    "headers": [],
                    "rows": [],
                    "warnings": ["Select a worksheet before mapping columns."],
                    "suggested_mapping": {},
                }
        headers, raw_rows, warnings, sheets = _xlsx_rows(data, sheet)
        rows = [
            {key: "" if value is None else str(value)[:200] for key, value in row.items()}
            for row in raw_rows[:PREVIEW_ROWS]
        ]
    else:
        dataset = (
            parse_gedcom(data, encoding) if suffix in {".ged", ".gedcom"} else parse_json(data)
        )
        return {
            "format": "gedcom" if suffix in {".ged", ".gedcom"} else "json",
            "sheets": [],
            "requires_sheet": False,
            "headers": [],
            "rows": [
                {"id": person.id, "name": person.primary_name or ""}
                for person in dataset.people[:PREVIEW_ROWS]
            ],
            "people": len(dataset.people),
            "relationships": len(dataset.relationships),
            "warnings": dataset.metadata.get("parse_warnings", []),
            "suggested_mapping": {},
        }
    folded = {header.casefold(): header for header in headers}
    suggested = {folded[column]: column for column in CANONICAL_COLUMNS if column in folded}
    return {
        "format": suffix.removeprefix("."),
        "sheets": sheets,
        "requires_sheet": False,
        "headers": headers,
        "rows": rows,
        "warnings": warnings,
        "suggested_mapping": suggested,
    }


def parse_file(
    path: Path,
    *,
    encoding: str | None = None,
    sheet: str | None = None,
    delimiter: str = ",",
    column_mapping: dict[str, str] | None = None,
) -> Dataset:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ParseError(f"Unsupported file type: {suffix or '(none)'}")
    data = path.read_bytes()
    if suffix in {".ged", ".gedcom"}:
        return parse_gedcom(data, encoding)
    if suffix == ".csv":
        return parse_csv(data, encoding, delimiter, column_mapping)
    if suffix == ".xlsx":
        return parse_xlsx(data, sheet, column_mapping)
    return parse_json(data)
