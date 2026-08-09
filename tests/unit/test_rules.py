from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from zupulint.config import DEFAULT_CONFIG
from zupulint.engine import scan as legacy_scan
from zupulint.models import Dataset, GenealogyDate, Person, Relationship, RelationshipType
from zupulint.parsers import parse_file
from zupulint.rules import RULES, scan

ROOT = Path(__file__).parents[2]


def test_rule_package_and_legacy_import_share_one_engine() -> None:
    assert legacy_scan is scan


def test_rule_definitions_expose_complete_metadata() -> None:
    assert len(RULES) == 26
    for rule in RULES:
        assert rule.message
        assert rule.config_schema
        assert rule.evidence
        assert rule.documentation_url.endswith(f"#{rule.rule_id.lower()}")


def person(
    identifier: str,
    name: str,
    *,
    birth: int | None = None,
    death: int | None = None,
    living: bool | None = False,
) -> Person:
    return Person(
        id=identifier,
        primary_name=name,
        names=[name],
        birth=GenealogyDate(
            raw=str(birth) if birth else None,
            value=date(birth, 1, 1) if birth else None,
            precision="year" if birth else "unknown",
        ),
        death=GenealogyDate(
            raw=str(death) if death else None,
            value=date(death, 1, 1) if death else None,
            precision="year" if death else "unknown",
        ),
        living=living,
    )


def relation(identifier: str, kind: RelationshipType, left: str, right: str) -> Relationship:
    return Relationship(id=identifier, type=kind, from_person_id=left, to_person_id=right)


def rule_ids(dataset: Dataset, config: dict[str, Any] | None = None) -> set[str]:
    return {issue.rule_id for issue in scan(dataset, config).issues}


def test_rule_definitions_expose_every_required_field() -> None:
    assert len(RULES) == 26
    assert len({rule.rule_id for rule in RULES}) == len(RULES)
    for rule in RULES:
        assert rule.title and rule.description and rule.category
        assert rule.default_severity in {"error", "warning", "info"}
        assert rule.config_schema and rule.evidence and rule.suggestion
        assert rule.documentation_url.startswith("https://")


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        (
            "invalid-structure.ged",
            {"ZP001", "ZP002", "ZP003", "ZP004", "ZP005", "ZP006"},
        ),
        (
            "invalid-chronology.json",
            {"ZP101", "ZP102", "ZP103", "ZP104", "ZP105"},
        ),
        (
            "invalid-generation.json",
            {"ZP201", "ZP202", "ZP203", "ZP204"},
        ),
        (
            "invalid-adoption.json",
            {"ZP301", "ZP302", "ZP303", "ZP304"},
        ),
        ("privacy-risk.csv", {"ZP501", "ZP503"}),
    ],
)
def test_committed_fixtures_trigger_rule_families(fixture: str, expected: set[str]) -> None:
    dataset = parse_file(ROOT / "examples" / "invalid" / fixture)
    assert expected <= rule_ids(dataset)


def test_valid_fixture_has_no_findings() -> None:
    result = scan(parse_file(ROOT / "examples" / "valid" / "family.ged"))
    assert result.summary == {
        "people": 16,
        "relationships": 24,
        "issues": 0,
        "by_severity": {},
        "by_rule": {},
    }


def test_cycle_evidence_uses_a_stable_rotation() -> None:
    dataset = Dataset(
        people=[person("P3", "三"), person("P1", "一"), person("P2", "二")],
        relationships=[
            relation("r3", RelationshipType.BIOLOGICAL_PARENT, "P3", "P1"),
            relation("r1", RelationshipType.BIOLOGICAL_PARENT, "P1", "P2"),
            relation("r2", RelationshipType.BIOLOGICAL_PARENT, "P2", "P3"),
        ],
    )

    issue = next(item for item in scan(dataset).issues if item.rule_id == "ZP004")
    assert issue.evidence["cycle"] == ["P1", "P2", "P3", "P1"]
    assert issue.message == "Biological ancestry cycle: P1 -> P2 -> P3 -> P1."


def test_duplicate_person_uses_all_evidence_without_merging() -> None:
    first = person("D1", "王绍明", birth=1900, death=1970)
    second = person("D2", "王绍明", birth=1900, death=1970)
    parent = person("P", "王浩父", birth=1870, death=1940)
    spouse = person("S", "配偶", birth=1905, death=1980)
    first.alias = ["王明"]
    second.alias = ["王明"]
    first.places = ["合成县"]
    second.places = ["合成县"]
    dataset = Dataset(
        people=[first, second, parent, spouse],
        relationships=[
            relation("p1", RelationshipType.BIOLOGICAL_PARENT, "P", "D1"),
            relation("p2", RelationshipType.BIOLOGICAL_PARENT, "P", "D2"),
            relation("s1", RelationshipType.SPOUSE, "D1", "S"),
            relation("s2", RelationshipType.SPOUSE, "D2", "S"),
        ],
    )
    issue = next(item for item in scan(dataset).issues if item.rule_id == "ZP401")
    assert issue.confidence == 1.0
    assert issue.evidence == {
        "name_similarity": 1.0,
        "same_birth_year": True,
        "same_death_year": True,
        "same_parents": True,
        "same_spouses": True,
        "same_place": True,
        "shared_alias": True,
    }
    assert len(dataset.people) == 4


def test_privacy_rule_never_puts_sensitive_values_in_evidence() -> None:
    minor = person("L1", "合成未成年", birth=date.today().year - 10, living=True)
    minor.privacy_level = "public"
    minor.places = ["合成市合成路一号"]
    minor.notes = ["phone 13800000000 DNA synthetic@example.invalid"]
    config = deepcopy(DEFAULT_CONFIG)
    config["privacy"]["redact_living_people"] = False
    issues = [
        item
        for item in scan(Dataset(people=[minor]), config).issues
        if item.rule_id.startswith("ZP5")
    ]
    assert {item.rule_id for item in issues} == {"ZP501", "ZP502", "ZP503"}
    rendered = str([item.to_dict() for item in issues])
    assert "13800000000" not in rendered
    assert "minor_details" in rendered


def test_quality_rules_cover_missing_unparsed_and_unsourced_claims() -> None:
    missing = person("", "", birth=1900)
    missing.birth = GenealogyDate(raw="traditional", precision="unparsed")
    config = deepcopy(DEFAULT_CONFIG)
    config["important_claims_require_sources"] = True
    dataset = Dataset(
        people=[missing, person("P2", "合成", birth=1900)],
        relationships=[
            Relationship(
                id="",
                type=RelationshipType.HEIR,
                from_person_id="P2",
                to_person_id="",
            )
        ],
        metadata={"parse_warnings": ["synthetic parser warning"]},
    )
    found = rule_ids(dataset, config)
    assert {"ZP601", "ZP602", "ZP603"} <= found


def test_configuration_disables_overrides_and_suppresses_info() -> None:
    dataset = Dataset(
        people=[Person(id="P1", primary_name=None)],
        metadata={"parse_warnings": ["warning"]},
    )
    config = deepcopy(DEFAULT_CONFIG)
    config["rules"]["severity"] = {"ZP601": "warning"}
    config["rules"]["disabled"] = ["ZP602"]
    result = scan(dataset, config)
    assert [(item.rule_id, item.severity) for item in result.issues] == [("ZP601", "warning")]

    config["rules"]["enabled"] = False
    assert not scan(dataset, config).issues

    config = deepcopy(DEFAULT_CONFIG)
    config["report"]["include_info"] = False
    assert "ZP602" not in rule_ids(dataset, config)


def test_historical_exception_and_sex_specific_age_thresholds() -> None:
    historical = person("H", "历史人物", birth=1600, death=1760)
    mother = person("M", "母", birth=1900)
    mother.sex = "F"
    child = person("C", "子", birth=1970)
    config = deepcopy(DEFAULT_CONFIG)
    config["chronology"]["historical_people"] = ["H"]
    result = scan(
        Dataset(
            people=[historical, mother, child],
            relationships=[relation("r", RelationshipType.BIOLOGICAL_PARENT, "M", "C")],
        ),
        config,
    )
    ids = {item.rule_id for item in result.issues}
    assert "ZP105" not in ids
    assert "ZP103" in ids


def test_issue_dictionary_always_contains_contract_fields() -> None:
    issue = scan(Dataset(people=[Person(id="P1")])).issues[0].to_dict()
    assert {
        "rule_id",
        "severity",
        "category",
        "message",
        "person_ids",
        "relationship_ids",
        "source_location",
        "evidence",
        "suggestion",
        "confidence",
    } <= issue.keys()
