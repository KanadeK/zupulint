"""Local-only living-person and sensitive-field detection."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from zupulint.models import Person
from zupulint.normalizers import year_delta

SENSITIVE_PATTERNS = {
    "phone": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "national_id": re.compile(r"(?<!\d)\d{17}[\dXx](?!\w)"),
    "email": re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    "address": re.compile(r"(?:省|市|区|县|路|街|号|栋|室)"),
    "medical": re.compile(r"(?:病历|诊断|medical|diagnosis)", re.I),
    "dna": re.compile(r"(?:DNA|基因|染色体|haplogroup)", re.I),
}


def is_living(person: Person, config: dict[str, Any], *, today: date | None = None) -> bool:
    """Infer living status without persisting or exposing personal data."""

    if person.living is not None:
        return person.living
    if person.death.value is not None:
        return False
    if person.birth.value is None:
        return False
    reference_date = today or date.today()
    return bool(
        year_delta(person.birth.value, reference_date)
        < config["privacy"]["living_person_year_threshold"]
    )


def person_text(person: Person) -> str:
    """Combine only the fields inspected by privacy rules."""

    extras = " ".join(f"{key}: {value!s}" for key, value in sorted(person.extensions.items()))
    return " ".join([*person.notes, extras])


def sensitive_fields(person: Person) -> list[str]:
    """Return deterministic field categories, never the matched sensitive values."""

    text = person_text(person)
    fields = [name for name, pattern in SENSITIVE_PATTERNS.items() if pattern.search(text)]
    if person.birth.value and person.birth.precision == "day":
        fields.append("exact_birth_date")
    return sorted(fields)


__all__ = ["SENSITIVE_PATTERNS", "is_living", "person_text", "sensitive_fields"]
