"""Canonical, parser-independent genealogy models.

The models intentionally retain raw values and unknown fields.  Genealogy data is
often lossy or ambiguous, so normalization must never destroy the source evidence.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExtensibleModel(BaseModel):
    """Base model that preserves forward-compatible JSON fields."""

    model_config = ConfigDict(extra="allow")


class RelationshipType(StrEnum):
    BIOLOGICAL_PARENT = "biological_parent"
    ADOPTIVE_PARENT = "adoptive_parent"
    STEP_PARENT = "step_parent"
    GUARDIAN = "guardian"
    SPOUSE = "spouse"
    PARTNER = "partner"
    ADOPTED_CHILD = "adopted_child"
    HEIR = "heir"
    POSTHUMOUS_HEIR = "posthumous_heir"
    UXORILOCAL = "uxorilocal"
    CHU_SI = "chu_si"
    CHENG_SI = "cheng_si"
    JIAN_TIAO = "jian_tiao"
    RU_ZHUI = "ru_zhui"
    JI_SI = "ji_si"
    GUO_JI = "guo_ji"


RELATIONSHIP_DISPLAY_ZH: dict[RelationshipType, str] = {
    RelationshipType.BIOLOGICAL_PARENT: "生父母",
    RelationshipType.ADOPTIVE_PARENT: "养父母",
    RelationshipType.STEP_PARENT: "继父母",
    RelationshipType.GUARDIAN: "监护",
    RelationshipType.SPOUSE: "配偶",
    RelationshipType.PARTNER: "伴侣",
    RelationshipType.ADOPTED_CHILD: "养子女",
    RelationshipType.HEIR: "继承",
    RelationshipType.POSTHUMOUS_HEIR: "追继",
    RelationshipType.UXORILOCAL: "入赘",
    RelationshipType.CHU_SI: "出嗣",
    RelationshipType.CHENG_SI: "承嗣",
    RelationshipType.JIAN_TIAO: "兼祧",
    RelationshipType.RU_ZHUI: "入赘",
    RelationshipType.JI_SI: "继嗣",
    RelationshipType.GUO_JI: "过继",
}


class GenealogyDate(ExtensibleModel):
    raw: str | None = None
    value: date | None = None
    end_value: date | None = None
    precision: Literal["unknown", "year", "month", "day", "range", "unparsed"] = "unknown"
    qualifier: Literal[
        "exact", "about", "calculated", "estimated", "before", "after", "between", "unknown"
    ] = "unknown"


class Event(ExtensibleModel):
    id: str
    person_id: str
    type: str
    date: GenealogyDate = Field(default_factory=GenealogyDate)
    place: str | None = None
    description: str | None = None
    sources: list[str] = Field(default_factory=list)

    @field_validator("date", mode="before")
    @classmethod
    def normalize_date(cls, value: Any) -> Any:
        if isinstance(value, (str, date)) or value is None:
            from zupulint.normalizers import parse_date

            return parse_date(value)
        return value


class Source(ExtensibleModel):
    id: str
    title: str | None = None
    type: str | None = None
    citation: str | None = None
    page: str | None = None
    url: str | None = None
    repository: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Person(ExtensibleModel):
    id: str
    names: list[str] = Field(default_factory=list)
    primary_name: str | None = None
    surname: str | None = None
    given_name: str | None = None
    generation_name: str | None = None
    courtesy_name: str | None = None
    alias: list[str] = Field(default_factory=list)
    sex: str | None = None
    birth: GenealogyDate = Field(default_factory=GenealogyDate)
    death: GenealogyDate = Field(default_factory=GenealogyDate)
    living: bool | None = None
    places: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    privacy_level: str = "private"
    branch: str | None = None
    generation: int | None = None
    extensions: dict[str, Any] = Field(default_factory=dict)

    @field_validator("birth", "death", mode="before")
    @classmethod
    def normalize_dates(cls, value: Any) -> Any:
        if isinstance(value, (str, date)) or value is None:
            from zupulint.normalizers import parse_date

            return parse_date(value)
        return value


class Relationship(ExtensibleModel):
    id: str
    type: RelationshipType
    from_person_id: str
    to_person_id: str
    start_date: GenealogyDate = Field(default_factory=GenealogyDate)
    end_date: GenealogyDate = Field(default_factory=GenealogyDate)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def normalize_dates(cls, value: Any) -> Any:
        if isinstance(value, (str, date)) or value is None:
            from zupulint.normalizers import parse_date

            return parse_date(value)
        return value


class Dataset(ExtensibleModel):
    people: list[Person] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
