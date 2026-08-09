from __future__ import annotations

from datetime import date

from zupulint.config import DEFAULT_CONFIG
from zupulint.models import Person
from zupulint.privacy import is_living, sensitive_fields


def test_living_status_respects_explicit_status_and_age_threshold() -> None:
    reference = date(2026, 8, 9)
    assert is_living(Person(id="P1", living=True), DEFAULT_CONFIG, today=reference)
    assert not is_living(Person(id="P2", living=False), DEFAULT_CONFIG, today=reference)
    assert is_living(
        Person.model_validate({"id": "P3", "birth": "2000-01-01"}),
        DEFAULT_CONFIG,
        today=reference,
    )
    assert not is_living(
        Person.model_validate({"id": "P4", "birth": "1800-01-01"}),
        DEFAULT_CONFIG,
        today=reference,
    )
    assert not is_living(
        Person.model_validate({"id": "P5", "death": "2020-01-01"}),
        DEFAULT_CONFIG,
        today=reference,
    )


def test_sensitive_detection_returns_categories_not_values() -> None:
    person = Person.model_validate(
        {
            "id": "SYNTHETIC-P1",
            "birth": "2010-05-06",
            "notes": ["SYNTHETIC ONLY 13800138000 fake@example.test 病历 DNA"],
            "extensions": {"address": "虚构市测试路1号"},
        }
    )
    fields = sensitive_fields(person)
    assert fields == ["address", "dna", "email", "exact_birth_date", "medical", "phone"]
    assert "13800138000" not in repr(fields)
