"""Deterministic rule engine shared by CLI, API and web UI."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

import networkx as nx
from rapidfuzz.fuzz import ratio

from zupulint.config import DEFAULT_CONFIG
from zupulint.models import Dataset, Person, Relationship, RelationshipType
from zupulint.normalizers import year_delta
from zupulint.privacy import is_living, sensitive_fields


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    title: str
    description: str
    category: str
    default_severity: str
    suggestion: str
    config_schema: dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": {"type": "boolean"},
            "severity": {"enum": ["error", "warning", "info"]},
        }
    )
    evidence: tuple[str, ...] = ("person_ids", "relationship_ids", "source_location")
    message: str = ""
    documentation_url: str = ""

    def __post_init__(self) -> None:
        if not self.message:
            object.__setattr__(self, "message", self.description)
        if not self.documentation_url:
            object.__setattr__(
                self,
                "documentation_url",
                f"https://kanadek.github.io/zupulint/rules/#{self.rule_id.lower()}",
            )


@dataclass(frozen=True)
class Issue:
    rule_id: str
    severity: str
    category: str
    message: str
    person_ids: tuple[str, ...] = ()
    relationship_ids: tuple[str, ...] = ()
    source_location: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    suggestion: str = ""
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {
            "person_ids": list(self.person_ids),
            "relationship_ids": list(self.relationship_ids),
        }


RULES = [
    RuleDefinition(
        "ZP001",
        "Duplicate person ID",
        "Two or more people share an ID.",
        "structure",
        "error",
        "Assign a unique stable ID.",
    ),
    RuleDefinition(
        "ZP002",
        "Missing reference",
        "A relationship points to an absent person.",
        "structure",
        "error",
        "Correct the reference or add the person.",
    ),
    RuleDefinition(
        "ZP003",
        "Self relationship",
        "A person relates to themselves.",
        "structure",
        "error",
        "Remove the self-reference.",
    ),
    RuleDefinition(
        "ZP004",
        "Ancestry cycle",
        "Biological parent ancestry contains a cycle.",
        "structure",
        "error",
        "Break the ancestral loop.",
    ),
    RuleDefinition(
        "ZP005",
        "Duplicate relationship",
        "The same relationship is recorded more than once.",
        "structure",
        "warning",
        "Keep one canonical relationship.",
    ),
    RuleDefinition(
        "ZP006",
        "Conflicting relationship roles",
        "Relationship roles for the same pair conflict.",
        "structure",
        "warning",
        "Review the pair's roles.",
    ),
    RuleDefinition(
        "ZP101",
        "Birth/death inversion",
        "Death precedes birth.",
        "chronology",
        "error",
        "Correct one of the dates.",
    ),
    RuleDefinition(
        "ZP102",
        "Child older than parent",
        "A child was born before a biological parent.",
        "chronology",
        "error",
        "Review parentage or dates.",
    ),
    RuleDefinition(
        "ZP103",
        "Unusual parent age",
        "Parent age at birth is outside configured thresholds.",
        "chronology",
        "warning",
        "Confirm the date and relationship.",
    ),
    RuleDefinition(
        "ZP104",
        "Marriage time conflict",
        "A partnership interval conflicts with its dates or deaths.",
        "chronology",
        "warning",
        "Correct marriage or death dates.",
    ),
    RuleDefinition(
        "ZP105",
        "Unusual lifespan",
        "Lifespan exceeds the configured limit.",
        "chronology",
        "warning",
        "Mark an historical exception or verify dates.",
    ),
    RuleDefinition(
        "ZP201",
        "Generation jump",
        "Parent and child generations do not differ by one.",
        "generation",
        "warning",
        "Correct the generation numbers.",
    ),
    RuleDefinition(
        "ZP202",
        "Sibling generation mismatch",
        "Children of a parent have inconsistent generations.",
        "generation",
        "warning",
        "Review sibling generation assignments.",
    ),
    RuleDefinition(
        "ZP203",
        "Generation-character mismatch",
        "Configured generation character conflicts with name or assigned generation.",
        "generation",
        "warning",
        "Review the branch poem or generation field.",
    ),
    RuleDefinition(
        "ZP204",
        "Missing branch generation poem",
        "A declared branch lacks a configured generation poem.",
        "generation",
        "warning",
        "Add its branch poem or correct the branch.",
    ),
    RuleDefinition(
        "ZP301",
        "Biological/successor parent conflict",
        "Biological and adoptive/successor roles overlap ambiguously.",
        "adoption",
        "warning",
        "Preserve both roles with separate relationships.",
    ),
    RuleDefinition(
        "ZP302",
        "Succession direction conflict",
        "Chu-si and cheng-si directions are inconsistent.",
        "adoption",
        "error",
        "Correct source and target succession families.",
    ),
    RuleDefinition(
        "ZP303",
        "Inheritance chain conflict",
        "A person has mutually exclusive inheritance identities.",
        "adoption",
        "warning",
        "Keep one inheritance identity per target.",
    ),
    RuleDefinition(
        "ZP304",
        "Incomplete jian-tiao",
        "Jian-tiao must name two successor branches.",
        "adoption",
        "warning",
        "Record both linked branches or heirs.",
    ),
    RuleDefinition(
        "ZP401",
        "Possible duplicate person",
        "People have strongly similar identity evidence.",
        "duplicate",
        "warning",
        "Review; ZupuLint never merges people automatically.",
    ),
    RuleDefinition(
        "ZP501",
        "Living sensitive data",
        "A living person contains sensitive data.",
        "privacy",
        "warning",
        "Redact or restrict the record.",
    ),
    RuleDefinition(
        "ZP502",
        "Unsafe report settings",
        "Configured output can expose living-person sensitive data.",
        "privacy",
        "warning",
        "Enable redaction and disable sensitive output.",
    ),
    RuleDefinition(
        "ZP503",
        "Privacy state conflict",
        "A public person contains high-sensitivity data.",
        "privacy",
        "error",
        "Make the record private or remove sensitive data.",
    ),
    RuleDefinition(
        "ZP601",
        "Required field missing",
        "A person or relationship lacks a required field.",
        "quality",
        "error",
        "Supply the missing identifier, name, or endpoint.",
    ),
    RuleDefinition(
        "ZP602",
        "Unparsed date",
        "A date was retained but could not be normalized.",
        "quality",
        "info",
        "Use a supported date or retain an evidence note.",
    ),
    RuleDefinition(
        "ZP603",
        "Important claim without source",
        "Configured important claims require a source.",
        "quality",
        "warning",
        "Add a source citation.",
    ),
]
RULE_BY_ID = {rule.rule_id: rule for rule in RULES}
PARENT_TYPES = {RelationshipType.BIOLOGICAL_PARENT}
ADOPTION_TYPES = {RelationshipType.ADOPTIVE_PARENT, RelationshipType.JI_SI, RelationshipType.GUO_JI}
SPOUSE_TYPES = {RelationshipType.SPOUSE, RelationshipType.PARTNER}
HEIR_TYPES = {RelationshipType.HEIR, RelationshipType.POSTHUMOUS_HEIR, RelationshipType.CHENG_SI}


def _issue(
    rule_id: str,
    message: str,
    *,
    people: list[str] | tuple[str, ...] = (),
    relationships: list[str] | tuple[str, ...] = (),
    evidence: dict[str, Any] | None = None,
    confidence: float = 1.0,
    config: dict[str, Any],
) -> Issue:
    rule = RULE_BY_ID[rule_id]
    severity = config["rules"].get("severity", {}).get(rule_id, rule.default_severity)
    return Issue(
        rule_id,
        severity,
        rule.category,
        message,
        tuple(sorted(people)),
        tuple(sorted(relationships)),
        evidence=evidence or {},
        suggestion=rule.suggestion,
        confidence=confidence,
    )


def _canonical_cycle(nodes: list[str]) -> tuple[str, ...]:
    """Rotate a directed cycle to its lexicographically smallest representation."""

    if not nodes:
        return ()
    return min(tuple(nodes[index:] + nodes[:index]) for index in range(len(nodes)))


def _validate_structure(dataset: Dataset, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    ids = [person.id for person in dataset.people]
    for person_id, count in sorted(Counter(ids).items()):
        if count > 1:
            issues.append(
                _issue(
                    "ZP001",
                    f"Person ID '{person_id}' occurs {count} times.",
                    people=[person_id],
                    evidence={"count": count},
                    config=config,
                )
            )
    valid_ids = set(ids)
    for rel in dataset.relationships:
        missing = sorted(
            {member for member in (rel.from_person_id, rel.to_person_id) if member not in valid_ids}
        )
        if missing:
            issues.append(
                _issue(
                    "ZP002",
                    f"Relationship '{rel.id}' references missing person(s): {', '.join(missing)}.",
                    people=missing,
                    relationships=[rel.id],
                    evidence={"missing_ids": missing},
                    config=config,
                )
            )
        if rel.from_person_id == rel.to_person_id:
            issues.append(
                _issue(
                    "ZP003",
                    f"Relationship '{rel.id}' relates '{rel.from_person_id}' to themselves.",
                    people=[rel.from_person_id],
                    relationships=[rel.id],
                    config=config,
                )
            )
    graph: nx.DiGraph[str, dict[str, Any]] = nx.DiGraph()
    graph.add_edges_from(
        (rel.from_person_id, rel.to_person_id, {"id": rel.id})
        for rel in dataset.relationships
        if rel.type in PARENT_TYPES
    )
    cycles = sorted({_canonical_cycle(cycle) for cycle in nx.simple_cycles(graph)})
    for canonical_cycle in cycles:
        cycle = list(canonical_cycle)
        cycle_ids = cycle + [cycle[0]]
        rel_ids = [
            str(graph[cycle_ids[index]][cycle_ids[index + 1]]["id"]) for index in range(len(cycle))
        ]
        issues.append(
            _issue(
                "ZP004",
                f"Biological ancestry cycle: {' -> '.join(cycle_ids)}.",
                people=cycle,
                relationships=rel_ids,
                evidence={"cycle": cycle_ids},
                config=config,
            )
        )
    seen: dict[tuple[Any, ...], Relationship] = {}
    for rel in dataset.relationships:
        endpoints = (
            tuple(sorted((rel.from_person_id, rel.to_person_id)))
            if rel.type in SPOUSE_TYPES
            else (rel.from_person_id, rel.to_person_id)
        )
        key = (rel.type, *endpoints, rel.start_date.raw, rel.end_date.raw)
        if key in seen:
            issues.append(
                _issue(
                    "ZP005",
                    f"Relationship '{rel.id}' duplicates '{seen[key].id}'.",
                    people=list(endpoints),
                    relationships=[seen[key].id, rel.id],
                    config=config,
                )
            )
        else:
            seen[key] = rel
    by_pair: dict[tuple[str, str], list[Relationship]] = defaultdict(list)
    for rel in dataset.relationships:
        by_pair[
            (rel.from_person_id, rel.to_person_id)
            if rel.from_person_id <= rel.to_person_id
            else (rel.to_person_id, rel.from_person_id)
        ].append(rel)
    conflicting = [
        (RelationshipType.BIOLOGICAL_PARENT, RelationshipType.SPOUSE),
        (RelationshipType.BIOLOGICAL_PARENT, RelationshipType.PARTNER),
        (RelationshipType.HEIR, RelationshipType.SPOUSE),
    ]
    for pair, rels in sorted(by_pair.items()):
        types = {rel.type for rel in rels}
        if any(left in types and right in types for left, right in conflicting):
            issues.append(
                _issue(
                    "ZP006",
                    f"Conflicting roles for '{pair[0]}' and '{pair[1]}': {', '.join(sorted(types))}.",
                    people=list(pair),
                    relationships=[rel.id for rel in rels],
                    evidence={"types": sorted(types)},
                    config=config,
                )
            )
    return issues


def _validate_chronology(dataset: Dataset, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    people = {person.id: person for person in dataset.people}
    for person in dataset.people:
        if person.birth.value and person.death.value:
            if person.death.value < person.birth.value:
                issues.append(
                    _issue(
                        "ZP101",
                        f"'{person.id}' dies before birth.",
                        people=[person.id],
                        config=config,
                    )
                )
            elif (
                person.id not in config["chronology"].get("historical_people", [])
                and year_delta(person.birth.value, person.death.value)
                > config["chronology"]["maximum_lifespan"]
            ):
                issues.append(
                    _issue(
                        "ZP105",
                        f"'{person.id}' lived more than {config['chronology']['maximum_lifespan']} years.",
                        people=[person.id],
                        evidence={"years": year_delta(person.birth.value, person.death.value)},
                        config=config,
                    )
                )
    for rel in dataset.relationships:
        if rel.type in PARENT_TYPES:
            parent, child = people.get(rel.from_person_id), people.get(rel.to_person_id)
            if parent and child and parent.birth.value and child.birth.value:
                age = year_delta(parent.birth.value, child.birth.value)
                if age < 0:
                    issues.append(
                        _issue(
                            "ZP102",
                            f"Child '{child.id}' predates parent '{parent.id}'.",
                            people=[parent.id, child.id],
                            relationships=[rel.id],
                            config=config,
                        )
                    )
                maximum = (
                    config["chronology"]["maximum_maternal_age"]
                    if parent.sex == "F"
                    else config["chronology"]["maximum_paternal_age"]
                )
                if age < config["chronology"]["minimum_parent_age"] or age > maximum:
                    issues.append(
                        _issue(
                            "ZP103",
                            f"Parent '{parent.id}' was {age} at '{child.id}' birth.",
                            people=[parent.id, child.id],
                            relationships=[rel.id],
                            evidence={"age": age, "maximum": maximum},
                            config=config,
                        )
                    )
        if rel.type in SPOUSE_TYPES:
            left, right = people.get(rel.from_person_id), people.get(rel.to_person_id)
            if (
                rel.start_date.value
                and rel.end_date.value
                and rel.start_date.value > rel.end_date.value
            ):
                issues.append(
                    _issue(
                        "ZP104",
                        f"Relationship '{rel.id}' ends before it starts.",
                        people=[rel.from_person_id, rel.to_person_id],
                        relationships=[rel.id],
                        config=config,
                    )
                )
            if rel.start_date.value and any(
                person and person.death.value and rel.start_date.value > person.death.value
                for person in (left, right)
            ):
                issues.append(
                    _issue(
                        "ZP104",
                        f"Relationship '{rel.id}' starts after a participant died.",
                        people=[rel.from_person_id, rel.to_person_id],
                        relationships=[rel.id],
                        config=config,
                    )
                )
    return issues


def _validate_generation(dataset: Dataset, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    people = {person.id: person for person in dataset.people}
    parent_children: dict[str, list[Person]] = defaultdict(list)
    poems = config["generation"].get("branch_generation_names", {})
    for rel in dataset.relationships:
        if rel.type in PARENT_TYPES:
            parent, child = people.get(rel.from_person_id), people.get(rel.to_person_id)
            if parent and child:
                parent_children[parent.id].append(child)
                if (
                    parent.generation is not None
                    and child.generation is not None
                    and child.generation - parent.generation != 1
                ):
                    issues.append(
                        _issue(
                            "ZP201",
                            f"Generation jump between '{parent.id}' ({parent.generation}) and '{child.id}' ({child.generation}).",
                            people=[parent.id, child.id],
                            relationships=[rel.id],
                            config=config,
                        )
                    )
    for parent_id, children in sorted(parent_children.items()):
        generations = sorted(
            {child.generation for child in children if child.generation is not None}
        )
        if len(generations) > 1:
            issues.append(
                _issue(
                    "ZP202",
                    f"Children of '{parent_id}' span generations {generations}.",
                    people=[parent_id, *[child.id for child in children]],
                    config=config,
                )
            )
    for person in dataset.people:
        if person.branch and person.branch not in poems:
            issues.append(
                _issue(
                    "ZP204",
                    f"Branch '{person.branch}' for '{person.id}' has no generation poem.",
                    people=[person.id],
                    config=config,
                )
            )
            continue
        poem = poems.get(person.branch or "main")
        if (
            poem
            and person.generation is not None
            and person.primary_name
            and person.primary_name not in config["generation"].get("ignore_names", [])
        ):
            expected_index = person.generation - config["generation"]["base_generation"]
            expected = poem[expected_index] if 0 <= expected_index < len(poem) else None
            actual = person.generation_name or next(
                (char for char in poem if char in person.primary_name), None
            )
            if expected and actual != expected:
                confidence = 1.0 if person.generation_name else 0.6
                issues.append(
                    _issue(
                        "ZP203",
                        f"'{person.id}' uses generation character '{actual or 'none found'}', expected '{expected}'.",
                        people=[person.id],
                        evidence={"expected": expected, "actual": actual},
                        confidence=confidence,
                        config=config,
                    )
                )
    return issues


def _validate_adoption(dataset: Dataset, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    by_child: dict[str, list[Relationship]] = defaultdict(list)
    for rel in dataset.relationships:
        if rel.type in PARENT_TYPES | ADOPTION_TYPES:
            by_child[rel.to_person_id].append(rel)
    for child, relations in sorted(by_child.items()):
        biological = [rel for rel in relations if rel.type in PARENT_TYPES]
        adoption = [rel for rel in relations if rel.type in ADOPTION_TYPES]
        if (
            biological
            and adoption
            and {rel.from_person_id for rel in biological}
            & {rel.from_person_id for rel in adoption}
        ):
            issues.append(
                _issue(
                    "ZP301",
                    f"'{child}' has the same parent recorded as biological and successor/adoptive.",
                    people=[child, *[rel.from_person_id for rel in relations]],
                    relationships=[rel.id for rel in relations],
                    config=config,
                )
            )
    outgoing_chu = {
        (rel.from_person_id, rel.to_person_id)
        for rel in dataset.relationships
        if rel.type == RelationshipType.CHU_SI
    }
    incoming_cheng = {
        (rel.to_person_id, rel.from_person_id)
        for rel in dataset.relationships
        if rel.type == RelationshipType.CHENG_SI
    }
    for source_target in sorted(outgoing_chu ^ incoming_cheng):
        issues.append(
            _issue(
                "ZP302",
                f"Succession direction '{source_target[0]}' -> '{source_target[1]}' lacks matching chu-si/cheng-si record.",
                people=list(source_target),
                evidence={"direction": source_target},
                config=config,
            )
        )
    heir_by_target: dict[str, list[Relationship]] = defaultdict(list)
    jian_tiao: dict[str, list[Relationship]] = defaultdict(list)
    for rel in dataset.relationships:
        if rel.type in HEIR_TYPES:
            heir_by_target[rel.to_person_id].append(rel)
        if rel.type == RelationshipType.JIAN_TIAO:
            jian_tiao[rel.from_person_id].append(rel)
    for target, relations in sorted(heir_by_target.items()):
        types = {rel.type for rel in relations}
        if len(relations) > 1 and len(types) > 1:
            issues.append(
                _issue(
                    "ZP303",
                    f"'{target}' has incompatible inheritance identities.",
                    people=[target, *[rel.from_person_id for rel in relations]],
                    relationships=[rel.id for rel in relations],
                    config=config,
                )
            )
    for person_id, relations in sorted(jian_tiao.items()):
        if len({rel.to_person_id for rel in relations}) < 2:
            issues.append(
                _issue(
                    "ZP304",
                    f"Jian-tiao for '{person_id}' has fewer than two successor branches.",
                    people=[person_id, *[rel.to_person_id for rel in relations]],
                    relationships=[rel.id for rel in relations],
                    config=config,
                )
            )
    return issues


def _validate_duplicates(dataset: Dataset, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    parent_sets: dict[str, set[str]] = defaultdict(set)
    spouse_sets: dict[str, set[str]] = defaultdict(set)
    for rel in dataset.relationships:
        if rel.type in PARENT_TYPES:
            parent_sets[rel.to_person_id].add(rel.from_person_id)
        if rel.type in SPOUSE_TYPES:
            spouse_sets[rel.from_person_id].add(rel.to_person_id)
            spouse_sets[rel.to_person_id].add(rel.from_person_id)
    for index, first in enumerate(dataset.people):
        for second in dataset.people[index + 1 :]:
            if not first.primary_name or not second.primary_name:
                continue
            name_score = ratio(first.primary_name, second.primary_name) / 100
            same_year = bool(
                first.birth.value
                and second.birth.value
                and first.birth.value.year == second.birth.value.year
            )
            same_death_year = bool(
                first.death.value
                and second.death.value
                and first.death.value.year == second.death.value.year
            )
            same_parents = bool(
                parent_sets[first.id] and parent_sets[first.id] == parent_sets[second.id]
            )
            same_spouses = bool(
                spouse_sets[first.id] and spouse_sets[first.id] == spouse_sets[second.id]
            )
            same_place = bool(set(first.places) & set(second.places))
            alias_evidence = bool(
                set(first.alias) & set(second.alias)
                or first.primary_name in second.alias
                or second.primary_name in first.alias
            )
            score = min(
                1.0,
                name_score * 0.62
                + (0.13 if same_year else 0)
                + (0.07 if same_death_year else 0)
                + (0.07 if same_parents else 0)
                + (0.04 if same_spouses else 0)
                + (0.04 if same_place else 0)
                + (0.03 if alias_evidence else 0),
            )
            if score >= 0.75:
                evidence = {
                    "name_similarity": round(name_score, 3),
                    "same_birth_year": same_year,
                    "same_death_year": same_death_year,
                    "same_parents": same_parents,
                    "same_spouses": same_spouses,
                    "same_place": same_place,
                    "shared_alias": alias_evidence,
                }
                issues.append(
                    _issue(
                        "ZP401",
                        f"'{first.id}' and '{second.id}' may describe the same person.",
                        people=[first.id, second.id],
                        evidence=evidence,
                        confidence=round(score, 3),
                        config=config,
                    )
                )
    return issues


def _validate_privacy(dataset: Dataset, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    unsafe_report = (
        not config["privacy"].get("redact_living_people", True)
        or config["privacy"].get("expose_exact_birth_date", False)
        or config["privacy"].get("expose_contact_details", False)
    )
    for person in dataset.people:
        sensitive = sensitive_fields(person)
        if not sensitive:
            continue
        living = is_living(person, config)
        if (
            living
            and person.birth.value
            and year_delta(person.birth.value, datetime.now(UTC).date()) < 18
            and (person.places or person.notes)
        ):
            sensitive = sorted({*sensitive, "minor_details"})
        if living:
            issues.append(
                _issue(
                    "ZP501",
                    f"Living person '{person.id}' contains: {', '.join(sensitive)}.",
                    people=[person.id],
                    evidence={"fields": sensitive},
                    config=config,
                )
            )
            if unsafe_report:
                issues.append(
                    _issue(
                        "ZP502",
                        f"Report configuration may expose '{person.id}' sensitive data.",
                        people=[person.id],
                        evidence={"fields": sensitive},
                        config=config,
                    )
                )
        if person.privacy_level == "public" and sensitive:
            issues.append(
                _issue(
                    "ZP503",
                    f"Public person '{person.id}' contains high-sensitivity data.",
                    people=[person.id],
                    evidence={"fields": sensitive},
                    config=config,
                )
            )
    return issues


def _validate_quality(dataset: Dataset, config: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    for person in dataset.people:
        missing = [
            field
            for field, value in (("id", person.id), ("primary_name", person.primary_name))
            if not value
        ]
        if missing:
            issues.append(
                _issue(
                    "ZP601",
                    f"Person has missing required field(s): {', '.join(missing)}.",
                    people=[person.id] if person.id else [],
                    evidence={"fields": missing},
                    config=config,
                )
            )
        for field_name, item_date in (("birth", person.birth), ("death", person.death)):
            if item_date.precision == "unparsed":
                issues.append(
                    _issue(
                        "ZP602",
                        f"'{person.id}' has unparsed {field_name} date '{item_date.raw}'.",
                        people=[person.id],
                        evidence={"raw": item_date.raw},
                        config=config,
                    )
                )
        if (
            config.get("important_claims_require_sources", False)
            and not person.sources
            and (person.birth.raw or person.death.raw or person.generation is not None)
        ):
            issues.append(
                _issue(
                    "ZP603",
                    f"Important claims for '{person.id}' lack a source.",
                    people=[person.id],
                    config=config,
                )
            )
    for relationship in dataset.relationships:
        if (
            config.get("important_claims_require_sources", False)
            and not relationship.sources
            and (
                relationship.type in HEIR_TYPES
                or relationship.type in ADOPTION_TYPES
                or relationship.start_date.raw
            )
        ):
            issues.append(
                _issue(
                    "ZP603",
                    f"Important relationship '{relationship.id}' lacks a source.",
                    relationships=[relationship.id],
                    people=[relationship.from_person_id, relationship.to_person_id],
                    config=config,
                )
            )
    for relationship in dataset.relationships:
        missing = [
            field
            for field, value in (
                ("id", relationship.id),
                ("from_person_id", relationship.from_person_id),
                ("to_person_id", relationship.to_person_id),
            )
            if not value
        ]
        if missing:
            issues.append(
                _issue(
                    "ZP601",
                    f"Relationship has missing required field(s): {', '.join(missing)}.",
                    relationships=[relationship.id] if relationship.id else [],
                    evidence={"fields": missing},
                    config=config,
                )
            )
    for warning in dataset.metadata.get("parse_warnings", []):
        issues.append(_issue("ZP602", str(warning), evidence={"parser": "input"}, config=config))
    return issues


VALIDATORS: tuple[Callable[[Dataset, dict[str, Any]], list[Issue]], ...] = (
    _validate_structure,
    _validate_chronology,
    _validate_generation,
    _validate_adoption,
    _validate_duplicates,
    _validate_privacy,
    _validate_quality,
)


@dataclass(frozen=True)
class ScanResult:
    issues: tuple[Issue, ...]
    people_count: int
    relationship_count: int
    config: dict[str, Any]
    scanned_at: str
    input_info: dict[str, Any] = field(default_factory=dict)

    @property
    def summary(self) -> dict[str, Any]:
        by_severity = Counter(issue.severity for issue in self.issues)
        by_rule = Counter(issue.rule_id for issue in self.issues)
        return {
            "people": self.people_count,
            "relationships": self.relationship_count,
            "issues": len(self.issues),
            "by_severity": dict(sorted(by_severity.items())),
            "by_rule": dict(sorted(by_rule.items())),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": "0.1.0",
            "scan": {"time": self.scanned_at, "input": self.input_info},
            "summary": self.summary,
            "issues": [issue.to_dict() for issue in self.issues],
            "config": self.config,
        }


def scan(
    dataset: Dataset,
    config: dict[str, Any] | None = None,
    *,
    input_info: dict[str, Any] | None = None,
    scanned_at: str | None = None,
) -> ScanResult:
    active_config = config or DEFAULT_CONFIG
    if not active_config["rules"].get("enabled", True):
        return ScanResult(
            (),
            len(dataset.people),
            len(dataset.relationships),
            active_config,
            scanned_at or datetime.now(UTC).isoformat(),
            input_info or {"format": dataset.metadata.get("input_format", "unknown")},
        )
    disabled = set(active_config["rules"].get("disabled", []))
    issues = [
        issue
        for validator in VALIDATORS
        for issue in validator(dataset, active_config)
        if issue.rule_id not in disabled
        and (active_config["report"].get("include_info", True) or issue.severity != "info")
    ]
    ordered = tuple(
        sorted(
            issues,
            key=lambda item: (item.rule_id, item.person_ids, item.relationship_ids, item.message),
        )
    )
    return ScanResult(
        ordered,
        len(dataset.people),
        len(dataset.relationships),
        active_config,
        scanned_at or datetime.now(UTC).isoformat(),
        input_info or {"format": dataset.metadata.get("input_format", "unknown")},
    )
