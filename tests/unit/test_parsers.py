from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from openpyxl import Workbook

from zupulint.models import RelationshipType
from zupulint.parsers.inputs import (
    ParseError,
    parse_csv,
    parse_file,
    parse_gedcom,
    parse_json,
    parse_xlsx,
    preview_data,
)


def workbook_bytes(
    rows: list[list[object]], *, second_sheet: bool = False, merge: bool = False
) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "People"
    for row in rows:
        sheet.append(row)
    if merge:
        sheet.merge_cells("A2:B2")
    if second_sheet:
        workbook.create_sheet("Notes").append(["synthetic"])
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def test_gedcom_tree_multiline_events_sources_and_extensions() -> None:
    payload = b"""0 HEAD
1 CHAR UTF-8
0 @S1@ SOUR
1 TITL Synthetic archive
1 AUTH Test author
1 TEXT Citation
1 REPO Local repository
0 @I1@ INDI
1 NAME Given /Family/
1 NAME Alias /Family/
1 NOTE first
2 CONT second
2 CONC joined
1 BIRT
2 DATE ABT 1900
2 PLAC Fictional place
2 SOUR @S1@
1 _CUSTOM retained
2 DATA nested
1 FAMC @MISSING@
0 TRLR
"""
    dataset = parse_gedcom(payload)
    person = dataset.people[0]
    assert person.primary_name == "Given Family"
    assert person.alias == ["Alias Family"]
    assert person.notes == ["first\nsecondjoined"]
    assert person.birth.qualifier == "about"
    assert dataset.events[0].place == "Fictional place"
    assert dataset.sources[0].title == "Synthetic archive"
    assert person.extensions["gedcom"][0]["tag"] == "_CUSTOM"
    assert "missing family" in " ".join(dataset.metadata["parse_warnings"])


def test_gedcom_structure_warnings_and_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    dataset = parse_gedcom(b"bad line\n2 NOTE orphan\n0 @I1@ INDI\n2 DATE 1900")
    warning_text = " ".join(dataset.metadata["parse_warnings"])
    assert "invalid GEDCOM syntax" in warning_text
    assert "orphaned" in warning_text
    assert "missing HEAD" in warning_text
    assert "missing TRLR" in warning_text

    import zupulint.parsers.inputs as inputs

    monkeypatch.setattr(inputs, "MAX_GEDCOM_LEVEL", 1)
    with pytest.raises(ParseError, match="level exceeds"):
        parse_gedcom(b"0 HEAD\n2 NOTE too-deep\n0 TRLR")
    monkeypatch.setattr(inputs, "MAX_GEDCOM_LINES", 1)
    with pytest.raises(ParseError, match="lines"):
        parse_gedcom(b"0 HEAD\n0 TRLR")
    monkeypatch.setattr(inputs, "MAX_INPUT_BYTES", 1)
    with pytest.raises(ParseError, match="20 MiB"):
        parse_gedcom(b"xx")


def test_checked_in_malformed_fixture_reports_structure_warnings() -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "malformed.ged"
    dataset = parse_file(fixture)
    warnings = " ".join(dataset.metadata["parse_warnings"])
    assert "illegal GEDCOM level jump" in warnings
    assert "missing TRLR" in warnings


def test_csv_encodings_delimiter_mapping_unknown_columns_and_relationships() -> None:
    text = "编号;姓名;出生;父母;配偶;附加\nP1;合成甲;1900;P0;P2;保留\n"
    dataset = parse_csv(
        text.encode("gb18030"),
        delimiter=";",
        column_mapping={
            "编号": "id",
            "姓名": "name",
            "出生": "birth",
            "父母": "parents",
            "配偶": "spouse",
        },
    )
    assert dataset.people[0].id == "P1"
    assert dataset.people[0].birth.value == date(1900, 1, 1)
    assert dataset.people[0].extensions == {"_source_row": 2, "附加": "保留"}
    assert {item.type for item in dataset.relationships} == {
        RelationshipType.BIOLOGICAL_PARENT,
        RelationshipType.SPOUSE,
    }


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"", "header"),
        (b"id,id\n1,2", "duplicate"),
    ],
)
def test_csv_rejects_bad_headers(payload: bytes, message: str) -> None:
    with pytest.raises(ParseError, match=message):
        parse_csv(payload)


def test_csv_rejects_bad_delimiter_and_encoding() -> None:
    with pytest.raises(ParseError, match="one character"):
        parse_csv(b"id,name", delimiter="::")
    with pytest.raises(ParseError, match="decode"):
        parse_csv(b"\xff", encoding="ascii")


def test_csv_row_and_column_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    import zupulint.parsers.inputs as inputs

    monkeypatch.setattr(inputs, "MAX_TABULAR_ROWS", 1)
    with pytest.raises(ParseError, match="data rows"):
        parse_csv(b"id,name\nP1,One\nP2,Two\n")
    monkeypatch.setattr(inputs, "MAX_TABULAR_COLUMNS", 1)
    with pytest.raises(ParseError, match="columns"):
        parse_csv(b"id,name\nP1,One\n")


def test_xlsx_dates_blank_rows_merged_cells_and_formula_safety() -> None:
    payload = workbook_bytes(
        [
            ["id", "name", "birth", "notes"],
            ["P1", "合成", date(1900, 1, 2), '=HYPERLINK("x")'],
            [None, None, None, None],
        ],
        merge=True,
    )
    dataset = parse_xlsx(payload)
    assert len(dataset.people) == 1
    assert dataset.people[0].birth.value == date(1900, 1, 2)
    warnings = " ".join(dataset.metadata["parse_warnings"])
    assert "merged cells" in warnings
    assert "formula-like" in warnings


def test_xlsx_requires_sheet_and_validates_headers() -> None:
    multi = workbook_bytes([["id", "name"], ["P1", "合成"]], second_sheet=True)
    with pytest.raises(ParseError, match="multiple worksheets"):
        parse_xlsx(multi)
    with pytest.raises(ParseError, match="Worksheet not found"):
        parse_xlsx(multi, "Absent")
    assert parse_xlsx(multi, "People").people[0].id == "P1"
    with pytest.raises(ParseError, match="duplicate"):
        parse_xlsx(workbook_bytes([["id", "id"], ["P1", "P2"]]))
    with pytest.raises(ParseError, match="header"):
        parse_xlsx(workbook_bytes([[None], ["P1"]]))
    with pytest.raises(ParseError, match="Invalid XLSX"):
        parse_xlsx(b"not a workbook")
    with pytest.raises(ParseError, match="Invalid XLSX"):
        preview_data(b"not a workbook", ".xlsx")


def test_xlsx_archive_and_sheet_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    import zupulint.parsers.inputs as inputs

    payload = workbook_bytes([["id", "name"], ["P1", "One"], ["P2", "Two"]])
    with monkeypatch.context() as context:
        context.setattr(inputs, "MAX_XLSX_MEMBERS", 1)
        with pytest.raises(ParseError, match="members"):
            parse_xlsx(payload)
    with monkeypatch.context() as context:
        context.setattr(inputs, "MAX_XLSX_UNCOMPRESSED_BYTES", 1)
        with pytest.raises(ParseError, match="decompression"):
            parse_xlsx(payload)
    with monkeypatch.context() as context:
        context.setattr(inputs, "MAX_INPUT_BYTES", len(payload))
        context.setattr(inputs, "MAX_XLSX_COMPRESSION_RATIO", 1)
        with pytest.raises(ParseError, match="compression ratio"):
            parse_xlsx(payload)
    with monkeypatch.context() as context:
        context.setattr(inputs, "MAX_TABULAR_ROWS", 1)
        with pytest.raises(ParseError, match="data rows"):
            parse_xlsx(payload)
    with monkeypatch.context() as context:
        context.setattr(inputs, "MAX_TABULAR_COLUMNS", 1)
        with pytest.raises(ParseError, match="columns"):
            parse_xlsx(payload)

    malicious = io.BytesIO()
    with ZipFile(malicious, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("../outside.xml", "synthetic")
    with pytest.raises(ParseError, match="unsafe internal path"):
        parse_xlsx(malicious.getvalue())


def test_json_validation_path_and_unknown_fields() -> None:
    dataset = parse_json(
        json.dumps(
            {
                "people": [{"id": "P1", "primary_name": "合成", "unknown": "retained"}],
                "relationships": [],
                "future": True,
            }
        ).encode()
    )
    assert dataset.people[0].model_extra == {"unknown": "retained"}
    assert dataset.model_extra == {"future": True}
    with pytest.raises(ParseError, match="top level"):
        parse_json(b"[]")
    with pytest.raises(ParseError, match="people.0.id|people.*id"):
        parse_json(b'{"people":[{"id":7}],"relationships":[]}')
    with pytest.raises(ParseError, match="Invalid ZupuLint JSON"):
        parse_json(b"{")


def test_json_depth_and_node_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    import zupulint.parsers.inputs as inputs

    nested: dict[str, object] = {}
    cursor = nested
    for _ in range(8):
        child: dict[str, object] = {}
        cursor["child"] = child
        cursor = child
    payload = json.dumps({"people": [], "relationships": [], "future": nested}).encode()
    with monkeypatch.context() as context:
        context.setattr(inputs, "MAX_JSON_DEPTH", 4)
        with pytest.raises(ParseError, match="nesting"):
            parse_json(payload)
    with monkeypatch.context() as context:
        context.setattr(inputs, "MAX_JSON_NODES", 2)
        with pytest.raises(ParseError, match="values"):
            parse_json(b'{"people":[],"relationships":[]}')


def test_preview_for_each_input_kind() -> None:
    csv_preview = preview_data(b"id,name\nP1,Synthetic\n", ".csv")
    assert csv_preview["headers"] == ["id", "name"]
    assert csv_preview["suggested_mapping"] == {"id": "id", "name": "name"}
    many_rows = b"id,name\n" + b"".join(
        f"P{index},Synthetic {index}\n".encode() for index in range(20)
    )
    assert len(preview_data(many_rows, ".csv")["rows"]) == 8

    multi = workbook_bytes([["id", "name"], ["P1", "Synthetic"]], second_sheet=True)
    pending = preview_data(multi, ".xlsx")
    assert pending["requires_sheet"] is True
    loaded = preview_data(multi, ".xlsx", sheet="People")
    assert loaded["rows"][0]["id"] == "P1"

    ged = preview_data(b"0 HEAD\n0 @I1@ INDI\n1 NAME A /B/\n0 TRLR", ".ged")
    assert ged["people"] == 1
    js = preview_data(b'{"people":[],"relationships":[]}', ".json")
    assert js["format"] == "json"


def test_parse_file_routes_and_rejects_unsupported(tmp_path: Path) -> None:
    payloads = {
        "one.ged": b"0 HEAD\n0 TRLR",
        "one.csv": b"id,name\nP1,Synthetic",
        "one.json": b'{"people":[],"relationships":[]}',
        "one.xlsx": workbook_bytes([["id", "name"], ["P1", "Synthetic"]]),
    }
    for name, payload in payloads.items():
        path = tmp_path / name
        path.write_bytes(payload)
        assert parse_file(path).metadata["input_format"] in {"gedcom", "csv", "json", "xlsx"}
    unknown = tmp_path / "one.txt"
    unknown.write_text("x", encoding="utf-8")
    with pytest.raises(ParseError, match="Unsupported"):
        parse_file(unknown)
