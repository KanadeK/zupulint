from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st
from openpyxl import Workbook

from zupulint.api.app import app
from zupulint.config import load_config
from zupulint.dates import parse_date
from zupulint.engine import RULES, scan
from zupulint.models import Dataset, GenealogyDate, Person, Relationship, RelationshipType
from zupulint.parsers.inputs import (
    ParseError,
    parse_csv,
    parse_file,
    parse_gedcom,
    parse_json,
    parse_xlsx,
)
from zupulint.reports import render_html, render_json, render_sarif

ROOT = Path(__file__).parents[1]


def person(pid: str, name: str = "测试") -> Person:
    return Person(
        id=pid,
        primary_name=name,
        names=[name],
        birth=GenealogyDate(value=date(1900, 1, 1), precision="year"),
        living=False,
    )


def rel(rid: str, kind: RelationshipType, left: str, right: str) -> Relationship:
    return Relationship(id=rid, type=kind, from_person_id=left, to_person_id=right)


def test_all_rules_are_real_definitions() -> None:
    assert len(RULES) == 26
    assert {rule.rule_id for rule in RULES} == {
        f"ZP{n:03d}"
        for n in [
            1,
            2,
            3,
            4,
            5,
            6,
            101,
            102,
            103,
            104,
            105,
            201,
            202,
            203,
            204,
            301,
            302,
            303,
            304,
            401,
            501,
            502,
            503,
            601,
            602,
            603,
        ]
    }


def test_gedcom_parser_reads_tree_and_warnings() -> None:
    data = b"0 HEAD\n1 CHAR UTF-8\n0 @I1@ INDI\n1 NAME /One/\n1 BIRT\n2 DATE 1900\n1 FAMS @F1@\n0 @F1@ FAM\n1 HUSB @I1@\n1 CHIL @I2@\n0 TRLR\n"
    dataset = parse_gedcom(data)
    assert dataset.people[0].id == "@I1@"
    assert dataset.people[0].birth.value == date(1900, 1, 1)
    assert dataset.relationships[0].to_person_id == "@I2@"
    assert dataset.metadata["parse_warnings"]


def test_csv_bom_and_relationships() -> None:
    dataset = parse_csv("\ufeffid,name,birth,parents\nP1,甲,1900,P0\n".encode())
    assert dataset.people[0].id == "P1"
    assert dataset.relationships[0].from_person_id == "P0"


def test_json_and_xlsx_imports() -> None:
    payload = {"people": [{"id": "P1", "primary_name": "甲"}], "relationships": []}
    assert parse_json(json.dumps(payload).encode()).people[0].primary_name == "甲"
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["id", "name", "birth"])
    sheet.append(["P1", "甲", "1900"])
    stream = io.BytesIO()
    workbook.save(stream)
    assert parse_xlsx(stream.getvalue()).people[0].id == "P1"


def test_parse_file_rejects_unknown_type() -> None:
    test_root = ROOT / ".pytest-tmp"
    test_root.mkdir(exist_ok=True)
    path = test_root / "input.txt"
    path.write_text("no", encoding="utf-8")
    try:
        parse_file(path)
    except ParseError as error:
        assert "Unsupported" in str(error)
    else:
        raise AssertionError("unsupported input was accepted")


def test_date_parser_is_lossless_on_unknown() -> None:
    parsed = parse_date("传统纪年未知")
    assert parsed.raw == "传统纪年未知"
    assert parsed.precision == "unparsed"


def test_structure_and_chronology_rules() -> None:
    people = [person("P1", "甲"), person("P2", "乙"), person("P2", "乙二")]
    people[0].birth = GenealogyDate(value=date(2000, 1, 1), precision="day")
    people[0].death = GenealogyDate(value=date(1990, 1, 1), precision="day")
    relationships = [
        rel("r1", RelationshipType.BIOLOGICAL_PARENT, "P1", "P1"),
        rel("r2", RelationshipType.BIOLOGICAL_PARENT, "P1", "P3"),
        rel("r3", RelationshipType.BIOLOGICAL_PARENT, "P1", "P2"),
        rel("r4", RelationshipType.BIOLOGICAL_PARENT, "P2", "P1"),
    ]
    result = scan(Dataset(people=people, relationships=relationships))
    found = {issue.rule_id for issue in result.issues}
    assert {"ZP001", "ZP002", "ZP003", "ZP004", "ZP101"} <= found


def test_generation_adoption_privacy_duplicate_rules() -> None:
    a = person("A", "甲守")
    b = person("B", "乙浩")
    a.generation = 1
    b.generation = 3
    b.living = True
    b.branch = "missing"
    b.privacy_level = "public"
    b.extensions = {"phone": "13800000000", "dna": "DNA synthetic"}
    dataset = Dataset(
        people=[a, b, person("C", "甲守")],
        relationships=[
            rel("p", RelationshipType.BIOLOGICAL_PARENT, "A", "B"),
            rel("ad", RelationshipType.ADOPTIVE_PARENT, "A", "B"),
            rel("h", RelationshipType.HEIR, "A", "B"),
            rel("h2", RelationshipType.POSTHUMOUS_HEIR, "C", "B"),
            rel("j", RelationshipType.JIAN_TIAO, "A", "B"),
        ],
    )
    result = scan(dataset)
    found = {issue.rule_id for issue in result.issues}
    assert {"ZP201", "ZP204", "ZP301", "ZP303", "ZP304", "ZP401", "ZP501", "ZP503"} <= found


def test_rule_configuration_and_deterministic_order() -> None:
    test_root = ROOT / ".pytest-tmp"
    test_root.mkdir(exist_ok=True)
    config = test_root / "config.yml"
    config.write_text("version: 1\nrules:\n  disabled: [ZP003]\n", encoding="utf-8")
    loaded = load_config(config)
    dataset = Dataset(
        people=[person("P1")], relationships=[rel("r", RelationshipType.SPOUSE, "P1", "P1")]
    )
    result = scan(dataset, loaded)
    assert "ZP003" not in {issue.rule_id for issue in result.issues}
    assert list(result.issues) == sorted(
        result.issues,
        key=lambda item: (item.rule_id, item.person_ids, item.relationship_ids, item.message),
    )


def test_reports_are_offline_and_sarif() -> None:
    result = scan(Dataset(people=[person("P1")]))
    html = render_html(result, "fixture.ged")
    assert "fixture.ged" in html and "http" not in html.replace("http://", "")
    assert json.loads(render_json(result))["version"] == "0.1.0"
    sarif = json.loads(render_sarif(result))
    assert sarif["version"] == "2.1.0"


def test_api_health_rules_and_scan() -> None:
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    assert len(client.get("/api/rules").json()) == 26
    response = client.post(
        "/api/scan",
        files={
            "file": (
                "sample.json",
                json.dumps({"people": [{"id": "P1", "primary_name": "甲"}], "relationships": []}),
                "application/json",
            )
        },
    )
    assert response.status_code == 200
    assert response.json()["summary"]["people"] == 1


@given(st.permutations(["P1", "P2", "P3"]))
def test_result_order_does_not_depend_on_people_input_order(order: list[str]) -> None:
    dataset = Dataset(
        people=[person(pid, pid) for pid in order],
        relationships=[rel("r", RelationshipType.BIOLOGICAL_PARENT, "P1", "P2")],
    )
    result = scan(dataset)
    assert [issue.to_dict() for issue in result.issues] == sorted(
        [issue.to_dict() for issue in result.issues],
        key=lambda item: (
            item["rule_id"],
            item["person_ids"],
            item["relationship_ids"],
            item["message"],
        ),
    )
