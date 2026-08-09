from __future__ import annotations

from datetime import date

import pytest

from zupulint.dates import parse_date as legacy_parse_date
from zupulint.models import (
    RELATIONSHIP_DISPLAY_ZH,
    Dataset,
    Event,
    Person,
    Relationship,
    RelationshipType,
)
from zupulint.normalizers import parse_date, year_delta


@pytest.mark.parametrize(
    ("raw", "value", "precision"),
    [
        (None, None, "unknown"),
        ("", None, "unknown"),
        (date(2020, 2, 3), date(2020, 2, 3), "day"),
        ("1900", date(1900, 1, 1), "year"),
        ("1900-05", date(1900, 5, 1), "month"),
        ("MAY 1900", date(1900, 5, 1), "month"),
        ("3 MAY 1900", date(1900, 5, 3), "day"),
        ("03/05/1900", date(1900, 5, 3), "day"),
        ("传统纪年", None, "unparsed"),
    ],
)
def test_exact_date_forms(raw: object, value: date | None, precision: str) -> None:
    parsed = parse_date(raw)
    assert parsed.value == value
    assert parsed.precision == precision
    assert parsed.raw is None if raw in (None, "") else parsed.raw


@pytest.mark.parametrize(
    ("prefix", "qualifier"),
    [
        ("ABT", "about"),
        ("CAL", "calculated"),
        ("EST", "estimated"),
        ("BEF", "before"),
        ("AFT", "after"),
    ],
)
def test_qualified_dates(prefix: str, qualifier: str) -> None:
    parsed = parse_date(f"{prefix} 1900")
    assert parsed.value == date(1900, 1, 1)
    assert parsed.qualifier == qualifier


@pytest.mark.parametrize("raw", ["BET 1900 AND 1905", "FROM 1900 TO 1905", "1900–1905"])
def test_date_ranges(raw: str) -> None:
    parsed = parse_date(raw)
    assert parsed.value == date(1900, 1, 1)
    assert parsed.end_value == date(1905, 1, 1)
    assert parsed.precision == "range"
    assert parsed.qualifier == "between"


def test_unparsed_range_retains_original() -> None:
    parsed = parse_date("BET traditional AND unknown")
    assert parsed.precision == "unparsed"
    assert parsed.raw == "BET traditional AND unknown"


def test_normalizer_public_api_and_legacy_import_match() -> None:
    assert legacy_parse_date is parse_date
    assert year_delta(date(2000, 8, 10), date(2026, 8, 9)) == 25


def test_models_normalize_dates_and_preserve_unknown_fields() -> None:
    person = Person.model_validate(
        {"id": "P1", "primary_name": "合成", "birth": "ABT 1900", "future_field": 7}
    )
    relationship = Relationship.model_validate(
        {
            "id": "R1",
            "type": "spouse",
            "from_person_id": "P1",
            "to_person_id": "P2",
            "start_date": "1920",
        }
    )
    event = Event.model_validate({"id": "E1", "person_id": "P1", "type": "birth", "date": "1900"})
    dataset = Dataset(people=[person], relationships=[relationship], events=[event])
    assert person.birth.qualifier == "about"
    assert person.model_extra == {"future_field": 7}
    assert relationship.start_date.value == date(1920, 1, 1)
    assert dataset.events[0].date.precision == "year"
    assert RELATIONSHIP_DISPLAY_ZH[RelationshipType.JIAN_TIAO] == "兼祧"
