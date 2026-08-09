"""Configuration loading, schema-level validation, and defaults."""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

SUPPORTED_RULE_IDS = {
    *(f"ZP00{index}" for index in range(1, 7)),
    *(f"ZP10{index}" for index in range(1, 6)),
    *(f"ZP20{index}" for index in range(1, 5)),
    *(f"ZP30{index}" for index in range(1, 5)),
    "ZP401",
    *(f"ZP50{index}" for index in range(1, 4)),
    *(f"ZP60{index}" for index in range(1, 4)),
}


class StrictConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RulesConfig(StrictConfigModel):
    enabled: bool = True
    disabled: list[str] = Field(default_factory=list)
    severity: dict[str, Literal["error", "warning", "info"]] = Field(default_factory=dict)


class ChronologyConfig(StrictConfigModel):
    minimum_parent_age: int = Field(default=12, ge=0, le=100)
    maximum_maternal_age: int = Field(default=60, ge=1, le=150)
    maximum_paternal_age: int = Field(default=90, ge=1, le=150)
    maximum_lifespan: int = Field(default=130, ge=1, le=500)
    historical_people: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_parent_ages(self) -> ChronologyConfig:
        if self.minimum_parent_age >= min(self.maximum_maternal_age, self.maximum_paternal_age):
            raise ValueError("minimum_parent_age must be below both maximum parent ages")
        return self


class GenerationConfig(StrictConfigModel):
    base_generation: int = 1
    branch_generation_names: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "main": ["守", "浩", "绍", "中", "德", "承", "先", "启", "后", "贤"]
        }
    )
    ignore_names: list[str] = Field(default_factory=list)


class PrivacyConfig(StrictConfigModel):
    redact_living_people: bool = True
    living_person_year_threshold: int = Field(default=110, ge=1, le=300)
    expose_exact_birth_date: bool = False
    expose_contact_details: bool = False


class ReportConfig(StrictConfigModel):
    include_info: bool = True
    include_evidence: bool = True
    include_suggestions: bool = True


class ZupuLintConfig(StrictConfigModel):
    version: Literal[1] = 1
    locale: Literal["zh-CN", "en"] = "zh-CN"
    rules: RulesConfig = Field(default_factory=RulesConfig)
    chronology: ChronologyConfig = Field(default_factory=ChronologyConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)
    important_claims_require_sources: bool = False


DEFAULT_CONFIG: dict[str, Any] = ZupuLintConfig().model_dump(mode="python")


def merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge an override without mutating either input."""

    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = value
    return result


def validate_config(content: dict[str, Any]) -> dict[str, Any]:
    try:
        validated = ZupuLintConfig.model_validate(content)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise ValueError(f"Invalid configuration: {details}") from exc
    invalid_rules = sorted(
        rule_id
        for rule_id in [
            *validated.rules.disabled,
            *validated.rules.severity.keys(),
        ]
        if not re.fullmatch(r"ZP\d{3}", rule_id) or rule_id not in SUPPORTED_RULE_IDS
    )
    if invalid_rules:
        raise ValueError(f"Invalid configuration: unknown rule IDs: {', '.join(invalid_rules)}")
    return validated.model_dump(mode="python")


def load_config(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        return deepcopy(DEFAULT_CONFIG)
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Invalid configuration: {exc}") from exc
    if not isinstance(content, dict):
        raise ValueError("Invalid configuration: top level must be a mapping")
    return validate_config(merge(DEFAULT_CONFIG, content))
