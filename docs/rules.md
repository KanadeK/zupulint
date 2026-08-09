# Rule reference

ZupuLint v0.1.0 has exactly 26 deterministic rules. Every finding contains a rule ID, category, severity, message, related person and relationship IDs, source location when available, structured evidence, confidence, and a repair suggestion. Results are stably sorted by rule ID, related IDs, and message.

All rules can be disabled with `rules.disabled: [ZP001]`; severities can be overridden with `rules.severity: {ZP001: warning}`. `rules.enabled: false` disables the entire engine. Those switches do not change parsing and never modify the input.

## Structure

<a id="zp001"></a>

### ZP001 — Duplicate person ID

- **Definition (default: error):** two or more canonical people use the same stable ID.
- **Detection:** count every `Person.id` after parsing; emit one finding per value whose count is greater than one, with the count as evidence.
- **Example:** two GEDCOM `INDI` records are both identified by `@I12@`.
- **Possible false positive:** an upstream export may intentionally reuse a display code, but that code is not safe as a canonical relationship key.
- **Configuration:** use the common disable/severity controls; there is no tolerance because canonical IDs must be unique.
- **Repair:** assign unique IDs and update every relationship, event, and source reference consistently.

<a id="zp002"></a>

### ZP002 — Missing reference

- **Definition (default: error):** a relationship endpoint names a person absent from the dataset.
- **Detection:** compare both endpoint IDs of every canonical relationship with the set of parsed person IDs.
- **Example:** `P1 biological_parent P9` exists, but no person has ID `P9`.
- **Possible false positive:** a deliberately partial extract can omit linked people; record a stub person or disable the rule only for that controlled extract.
- **Configuration:** common disable/severity controls.
- **Repair:** correct a mistyped pointer, add the missing person, or remove the unsupported relationship.

<a id="zp003"></a>

### ZP003 — Self relationship

- **Definition (default: error):** a relationship starts and ends at the same person.
- **Detection:** compare `from_person_id` and `to_person_id` for every relationship type.
- **Example:** `I7 spouse I7`.
- **Possible false positive:** none in the canonical model; self-referential notes should be modeled as notes, not relationships.
- **Configuration:** common disable/severity controls.
- **Repair:** replace the incorrect endpoint or remove the relationship.

<a id="zp004"></a>

### ZP004 — Biological ancestry cycle

- **Definition (default: error):** biological-parent edges contain a directed cycle.
- **Detection:** construct a directed graph from `biological_parent` relationships and enumerate simple cycles; adoption and succession edges are deliberately excluded.
- **Example:** `A` is parent of `B`, `B` of `C`, and `C` of `A`.
- **Possible false positive:** a historical record may reuse IDs for namesakes; that is usually an ID problem, not a valid ancestry cycle.
- **Configuration:** common disable/severity controls.
- **Repair:** inspect the reported cycle and correct the wrong person ID or parent edge; ZupuLint never removes it automatically.

<a id="zp005"></a>

### ZP005 — Duplicate relationship

- **Definition (default: warning):** the same typed and dated relationship is recorded more than once.
- **Detection:** compare type, endpoints, raw start date, and raw end date. Spouse/partner endpoints are treated as unordered; directed roles retain direction.
- **Example:** two spouse records connect `I1` and `I2` with the same dates.
- **Possible false positive:** two sources may independently attest the same fact; preserve both citations on one canonical relationship instead of duplicating the edge.
- **Configuration:** common disable/severity controls.
- **Repair:** retain one canonical relationship and consolidate its sources and notes.

<a id="zp006"></a>

### ZP006 — Conflicting relationship roles

- **Definition (default: warning):** a pair has roles that cannot normally coexist.
- **Detection:** flag a pair containing biological-parent plus spouse, biological-parent plus partner, or heir plus spouse roles.
- **Example:** `I1` is recorded both as biological parent and spouse of `I2`.
- **Possible false positive:** unusual source terminology may have been mapped to the wrong canonical type.
- **Configuration:** common disable/severity controls.
- **Repair:** review the source and correct the misclassified role while preserving legitimate distinct evidence.

## Chronology

<a id="zp101"></a>

### ZP101 — Birth/death inversion

- **Definition (default: error):** a normalized death date precedes the same person's birth date.
- **Detection:** compare normalized dates only when both are available; raw unparsed text is handled by ZP602.
- **Example:** birth `1950-01-01`, death `1949-12-31`.
- **Possible false positive:** calendar conversion or transcription uncertainty may place an approximate date on the wrong side of the comparison.
- **Configuration:** common disable/severity controls.
- **Repair:** verify the source, calendar, qualifier, and person identity; correct the erroneous date.

<a id="zp102"></a>

### ZP102 — Child predates parent

- **Definition (default: error):** a biological child is born before a biological parent.
- **Detection:** compare normalized birth dates on `biological_parent` edges; non-biological roles are excluded.
- **Example:** parent born in 1920 and child born in 1910.
- **Possible false positive:** the relationship may actually be adoptive or the records may describe namesakes.
- **Configuration:** common disable/severity controls.
- **Repair:** correct the dates, identity, or relationship type.

<a id="zp103"></a>

### ZP103 — Unusual parent age

- **Definition (default: warning):** parent age at a child's birth falls outside configured thresholds.
- **Detection:** calculate completed years for biological-parent edges. The default minimum is 12; the maximum is 60 for `sex: F` and 90 otherwise.
- **Example:** a parent is recorded as eight years old at the child's birth.
- **Possible false positive:** approximate years, uncertain sex data, calendar conversion, or exceptional historical evidence can require review.
- **Configuration:** set `chronology.minimum_parent_age`, `maximum_maternal_age`, or `maximum_paternal_age`, or use common controls.
- **Repair:** verify dates and parentage; change a threshold only when the collection's documented policy requires it.

<a id="zp104"></a>

### ZP104 — Partnership time conflict

- **Definition (default: warning):** a spouse/partner interval is internally reversed or starts after a participant's death.
- **Detection:** flag `start_date > end_date`, or a normalized start later than either participant's normalized death.
- **Example:** marriage begins in 1980 although one spouse died in 1978.
- **Possible false positive:** posthumous ceremonial records should be represented with explanatory evidence rather than an ordinary partnership start.
- **Configuration:** common disable/severity controls.
- **Repair:** correct the interval, participant, or canonical relationship type and retain the source note.

<a id="zp105"></a>

### ZP105 — Unusual lifespan

- **Definition (default: warning):** a normalized lifespan exceeds the configured maximum.
- **Detection:** compare birth and death in completed years; the default maximum is 130.
- **Example:** birth 1700 and death 1900 for one ID.
- **Possible false positive:** rare historical claims may be deliberately retained pending research.
- **Configuration:** set `chronology.maximum_lifespan`; list reviewed IDs in `chronology.historical_people`; or use common controls.
- **Repair:** split conflated people or correct dates; use the historical exception list only with documented evidence.

## Generations and generation characters

<a id="zp201"></a>

### ZP201 — Parent/child generation jump

- **Definition (default: warning):** assigned child generation is not exactly parent generation plus one.
- **Detection:** compare explicit integer `generation` values on biological-parent edges when both values exist.
- **Example:** parent generation 3 and child generation 5.
- **Possible false positive:** a collection may number social succession rather than biological descent; map that concept separately.
- **Configuration:** common disable/severity controls; `generation.base_generation` does not alter the one-step relationship check.
- **Repair:** correct the generation numbers or relationship type.

<a id="zp202"></a>

### ZP202 — Sibling generation mismatch

- **Definition (default: warning):** children of the same biological parent have different explicit generations.
- **Detection:** group biological children by parent and compare the set of non-null generation values.
- **Example:** two children of `P1` are assigned generations 4 and 5.
- **Possible false positive:** lineage systems that number descendants by house rather than descent may require separate branch modeling.
- **Configuration:** common disable/severity controls.
- **Repair:** verify the parent links and normalize sibling generation assignments.

<a id="zp203"></a>

### ZP203 — Generation-character mismatch

- **Definition (default: warning):** the configured character for a person's generation conflicts with the explicit or inferred character in the name.
- **Detection:** select the branch poem (or `main`), calculate `generation - base_generation`, and compare the expected character with `generation_name`; if absent, look for a poem character in `primary_name`. Explicit evidence has confidence 1.0; name inference has confidence 0.6.
- **Example:** generation 3 expects `绍`, but `generation_name` is `浩`.
- **Possible false positive:** married names, courtesy names, alternate character positions, homophones, and local branch exceptions can defeat inference.
- **Configuration:** set `generation.base_generation`, `generation.branch_generation_names`, and `generation.ignore_names`; common controls also apply.
- **Repair:** correct the explicit generation/character, select the right branch poem, or document and ignore a confirmed exception.

<a id="zp204"></a>

### ZP204 — Missing branch generation poem

- **Definition (default: warning):** a person declares a branch that has no configured generation-character list.
- **Detection:** compare every non-empty `Person.branch` with keys in `generation.branch_generation_names`.
- **Example:** a person uses branch `east`, while configuration defines only `main`.
- **Possible false positive:** a branch may intentionally not use generation characters, but that policy should be explicit.
- **Configuration:** add the branch key under `generation.branch_generation_names`, correct the input branch, or use common controls.
- **Repair:** provide the documented poem for that branch or correct the branch assignment.

## Adoption and succession

<a id="zp301"></a>

### ZP301 — Biological/successor parent overlap

- **Definition (default: warning):** the same adult is recorded for one child as both biological parent and adoptive/successor parent.
- **Detection:** for each child, intersect biological-parent sources with `adoptive_parent`, `ji_si`, and `guo_ji` sources.
- **Example:** `P1` is both biological and adoptive parent of `C1`.
- **Possible false positive:** a source may intentionally express multiple social roles, but each needs a clear, separate interpretation.
- **Configuration:** common disable/severity controls.
- **Repair:** preserve legitimate roles as distinct relationships; remove only the wrongly classified duplicate.

<a id="zp302"></a>

### ZP302 — Chu-si/cheng-si direction mismatch

- **Definition (default: error):** an `chu_si` direction lacks its inverse `cheng_si` record, or vice versa.
- **Detection:** compare `(source, target)` chu-si pairs with reversed `(target, source)` cheng-si pairs using symmetric set difference.
- **Example:** `A chu_si B` exists without `B cheng_si A`.
- **Possible false positive:** an incomplete extract may contain only one side of a documented succession.
- **Configuration:** common disable/severity controls.
- **Repair:** add the missing inverse record with evidence or correct the direction/role.

<a id="zp303"></a>

### ZP303 — Inheritance identity conflict

- **Definition (default: warning):** one target receives multiple incompatible heir identities.
- **Detection:** group `heir`, `posthumous_heir`, and `cheng_si` relationships by target; flag groups with multiple records spanning more than one type.
- **Example:** one target has both ordinary-heir and posthumous-heir records from different people.
- **Possible false positive:** sequential historical appointments may be valid when time intervals or source notes distinguish them; v0.1.0 still requests review.
- **Configuration:** common disable/severity controls.
- **Repair:** correct the type/target, add temporal evidence, or retain a single supported identity.

<a id="zp304"></a>

### ZP304 — Incomplete jian-tiao

- **Definition (default: warning):** a person's jian-tiao configuration names fewer than two distinct successor targets.
- **Detection:** group `jian_tiao` relationships by source person and count distinct targets.
- **Example:** `A jian_tiao B` is recorded without a second branch target.
- **Possible false positive:** the source may be a partial extract or record an unresolved appointment.
- **Configuration:** common disable/severity controls.
- **Repair:** add the second documented branch/target or remove the premature jian-tiao classification.

## Possible duplicate people

<a id="zp401"></a>

### ZP401 — Possible duplicate person

- **Definition (default: warning):** two different IDs have sufficiently similar identity evidence.
- **Detection:** score every named pair: name similarity 62%, matching birth year 13%, death year 7%, parent set 7%, spouse set 4%, place overlap 4%, and alias evidence 3%. Emit at score 0.75 or greater and expose each component.
- **Example:** two IDs have nearly identical names, the same birth year, and the same parents.
- **Possible false positive:** relatives may reuse names and share places or parents; the score is a review signal, not proof.
- **Configuration:** common disable/severity controls. The threshold is intentionally fixed in v0.1.0 for reproducible results.
- **Repair:** compare original sources and merge only in the source system after human confirmation; ZupuLint never merges automatically.

## Privacy

<a id="zp501"></a>

### ZP501 — Living-person sensitive data

- **Definition (default: warning):** a person considered living contains sensitive fields.
- **Detection:** honor explicit `living`; otherwise a death date means deceased, and a parsed birth less than `living_person_year_threshold` years ago means living. Detect exact day-level birth dates plus phone, national ID, email, address, medical, and DNA patterns in notes/extensions; flag extra minor details for living people under 18.
- **Example:** a living person's note contains a synthetic mobile number and address.
- **Possible false positive:** archival notes may quote another person's data or contain digit patterns with another meaning.
- **Configuration:** set `privacy.living_person_year_threshold` or common controls; explicit `living` data is preferred.
- **Repair:** remove or restrict sensitive content, mark privacy correctly, and keep public reports redacted.

<a id="zp502"></a>

### ZP502 — Unsafe report settings

- **Definition (default: warning):** report configuration may expose sensitive data belonging to a living person.
- **Detection:** when ZP501-sensitive content is present, flag if redaction is disabled, exact birth dates are exposed, or contact details are exposed.
- **Example:** `privacy.redact_living_people: false` while a living record contains an email address.
- **Possible false positive:** a private, access-controlled research export may be intentional; the warning documents the risk.
- **Configuration:** keep `redact_living_people: true`, `expose_exact_birth_date: false`, and `expose_contact_details: false`, or use common controls.
- **Repair:** restore safe settings before sharing or move the report into an appropriately controlled environment.

<a id="zp503"></a>

### ZP503 — Public/high-sensitivity conflict

- **Definition (default: error):** a person marked `privacy_level: public` contains sensitive data.
- **Detection:** apply the same sensitive-field detector as ZP501, regardless of living inference, to public records.
- **Example:** a public person record contains a national ID pattern.
- **Possible false positive:** a synthetic demonstration can intentionally contain fake data, but should remain clearly marked and private by default.
- **Configuration:** common disable/severity controls.
- **Repair:** remove the sensitive field or change the record's privacy level before distribution.

## Data quality

<a id="zp601"></a>

### ZP601 — Required field missing

- **Definition (default: error):** a canonical person lacks an ID or primary name, or a relationship lacks an ID or endpoint.
- **Detection:** check normalized values after parsing; schema/Pydantic failures may reject more fundamentally malformed JSON before the engine runs.
- **Example:** a CSV row has an ID but an empty display name.
- **Possible false positive:** unnamed or unidentified ancestors may be historically legitimate; give them a stable placeholder label with source context.
- **Configuration:** common disable/severity controls.
- **Repair:** supply stable IDs, labels, and endpoints without inventing unsupported identity claims.

<a id="zp602"></a>

### ZP602 — Unparsed date or parser warning

- **Definition (default: info):** date text was retained but not normalized, or a bounded parser detected a recoverable input problem.
- **Detection:** inspect `birth`/`death` values with precision `unparsed` and parser warnings such as malformed GEDCOM lines, missing terminators, dangling pointers, merged XLSX cells, or inert formula-like text.
- **Example:** birth text `late spring, reign year unknown` is preserved verbatim but cannot be compared chronologically.
- **Possible false positive:** traditional or uncertain dates can be valid evidence even when normalization is impossible.
- **Configuration:** common disable/severity controls; `report.include_info: false` omits informational findings.
- **Repair:** use a supported exact/partial/range/qualified date when evidence permits, otherwise retain the raw text and source note.

<a id="zp603"></a>

### ZP603 — Important claim without source

- **Definition (default: warning):** an important dated, generation, adoption, succession, or partnership claim lacks a source when source enforcement is enabled.
- **Detection:** with `important_claims_require_sources: true`, check dated/generation person claims and adoption, heir, or dated relationship claims for non-empty sources.
- **Example:** an heir relationship is present without a citation.
- **Possible false positive:** a working transcription may not yet have citations; keep this opt-in during staged cleanup.
- **Configuration:** enable with top-level `important_claims_require_sources: true`; common disable/severity controls also apply.
- **Repair:** add a source ID/citation or remove an unsupported claim; do not fabricate a citation.
