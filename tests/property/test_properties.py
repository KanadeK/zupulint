from __future__ import annotations

import json
from copy import deepcopy
from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from zupulint.config import DEFAULT_CONFIG
from zupulint.models import Dataset, GenealogyDate, Person, Relationship, RelationshipType
from zupulint.reports import render_html, render_json, render_sarif
from zupulint.rules import scan


def make_person(identifier: str) -> Person:
    return Person(id=identifier, primary_name=identifier, living=False)


@given(st.integers(min_value=1, max_value=30))
def test_any_linear_parent_tree_is_not_reported_as_a_cycle(size: int) -> None:
    people = [make_person(f"P{index}") for index in range(size)]
    relationships = [
        Relationship(
            id=f"R{index}",
            type=RelationshipType.BIOLOGICAL_PARENT,
            from_person_id=f"P{index}",
            to_person_id=f"P{index + 1}",
        )
        for index in range(size - 1)
    ]
    assert "ZP004" not in {
        item.rule_id for item in scan(Dataset(people=people, relationships=relationships)).issues
    }


@given(st.lists(st.text(min_size=1, max_size=8), min_size=1, max_size=10, unique=True))
def test_report_json_round_trip_is_stable(identifiers: list[str]) -> None:
    result = scan(
        Dataset(people=[make_person(item) for item in identifiers]),
        scanned_at="2026-01-01T00:00:00+00:00",
    )
    first = json.loads(render_json(result))
    second = json.loads(json.dumps(first, ensure_ascii=False, sort_keys=True))
    assert first == second


@given(st.sampled_from(["13800000000", "11000020000101001X", "DNA-ACTG", "合成市合成路一号"]))
def test_redacted_reports_do_not_retain_sensitive_source_text(secret: str) -> None:
    person = Person(
        id="L1",
        primary_name="合成人物",
        living=True,
        birth=GenealogyDate(value=date(2010, 1, 2), precision="day"),
        notes=[secret],
    )
    result = scan(Dataset(people=[person]), scanned_at="2026-01-01T00:00:00+00:00")
    assert secret not in render_json(result)
    assert secret not in render_html(result)
    assert secret not in render_sarif(result)


@given(st.permutations(["P1", "P2", "P3", "P4"]))
def test_input_order_does_not_change_issue_order(order: list[str]) -> None:
    people = [make_person(identifier) for identifier in order]
    relationships = [
        Relationship(
            id="self",
            type=RelationshipType.SPOUSE,
            from_person_id="P1",
            to_person_id="P1",
        )
    ]
    config = deepcopy(DEFAULT_CONFIG)
    issues = scan(Dataset(people=people, relationships=relationships), config).issues
    assert [item.to_dict() for item in issues] == sorted(
        [item.to_dict() for item in issues],
        key=lambda item: (
            item["rule_id"],
            item["person_ids"],
            item["relationship_ids"],
            item["message"],
        ),
    )
