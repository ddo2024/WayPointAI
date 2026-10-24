# Part 1 integration contracts, v1

The two JSON Schemas use Draft 2020-12. They reject extra fields so misspellings
do not silently change meaning. Both require `schema_version: "1.0.0"`, an exact
`vocabulary_version`, and a boolean `is_mock`. Validate each document against its
schema and validate the bundle for cross-file relationships; JSON Schema alone
cannot establish ID uniqueness by one field or verify arithmetic.

## Vocabulary

Top-level fields: `schema_version`, `vocabulary_version`, `is_mock`, `skills`.
Each skill requires `canonical_id`, `display_name`, `category`, `aliases`, and
`matching_policy`.

Canonical IDs such as `skill:postgresql` are project-owned identifiers. They are
not O*NET Element IDs. The current 16 entries are an illustrative mock vocabulary,
not a complete backend skill list or an inferred O*NET mapping. Source-derived
vocabulary mappings will need their own provenance artifact after review.

`display_name` is always a matching candidate; `aliases` contains additional
names. All candidates are literal strings, escaped before use in regex. Alias
collisions across canonical skills are rejected. Categories in this vocabulary
are project categories; they must not be presented as O*NET source categories.

## Matching policy shared by Parts 1 and 2

`waypoint_data.matching_policy.is_declared_match` is a reusable candidate-span
validator, not a resume parser or posting extractor. It defines these rules:

1. `case_sensitive` selects either no regex flags or Python `re.IGNORECASE`.
2. `technology_token_v1` wraps each escaped alias with
   `(?<![\w+#.])` before and `(?![\w+#]|\.\w)` after. Python Unicode `\w`
   includes letters, numbers, and underscore. Thus Java cannot match JavaScript,
   C cannot match C++, Git cannot match GitHub, and SQL cannot match PostgreSQL.
   A sentence-ending period is allowed, but an adjacent dotted-name suffix is not.
3. A context rule applies only to its exact declared `alias`. At least one of its
   `any_of_patterns` must match and **cover the same candidate span**. Patterns
   use the skill's case flags, with no DOTALL or MULTILINE. A different “Go
   programming” occurrence must not license “go to the office.” No rule for an
   alias means no additional context is required for that alias.
4. Go, R, and C require an adjacent programming/language/developer phrase in this
   conservative mock policy. `Golang` is an unambiguous alias. Bare skill-list
   mentions of Go/R/C may be missed intentionally until reviewed rules exist.
   `PG` is not a PostgreSQL alias.
5. The future extractor must evaluate candidate matches by descending matched
   length, then ascending start offset, canonical ID, and alias. Retain the first
   valid non-overlapping candidate; emit evidence ordered by offset and ID.
   This is the exact `longest_match_first` tie policy. No hierarchy inference is
   performed. Aliases may normalize names, never imply separate skills.

Version this policy through `vocabulary_version`; a rule change must not be
silently deployed to only one parser. Keep punctuation and original case in
evidence. Offsets refer to Unicode characters in `cleaned_text`, end-exclusive;
JavaScript consumers must account for UTF-16 offsets if highlighting text.

## Role profile

Top-level fields: `schema_version`, `vocabulary_version`, `is_mock`, `role_id`,
`display_title`, `onet_code`, `metadata`, `onet_skills`, `posting_skills`.

`metadata.filters` records occupation, specialization, seniority, and geography
independently, with the rules version and unknown/conflict exclusion policies.
`sources` records source identifier, type, URI, release/snapshot version,
collection date range (or null), and loaded/synthetic status. Collection dates
must stay null when unknown. `generated_at` is the export timestamp in UTC and
must never stand in for collection time.

`eligible_postings_count` counts retained postings passing all role filters.
`analyzed_postings_count` counts eligible postings with usable requirement text.
`excluded_unusable_descriptions_count` is **within the eligible set**, so:

```text
eligible_postings_count = analyzed_postings_count + excluded_unusable_descriptions_count
mention_count = number of distinct analyzed posting IDs with direct evidence for a skill
mention_rate = mention_count / analyzed_postings_count
```

Usable text with no detected skill stays in the denominator. Repeated skill
occurrences count once per posting. Rates are fractions from 0 to 1; the frontend
renders 0.6 as 60%. When the denominator is zero, rates are null, counts are zero,
evidence samples are empty, and `data_status` must be `insufficient_data`.
`is_mock` remains independent of that status.

`data_status` is `unassessed`, `insufficient_data`, `limited_sample`, or
`usable_sample`. A positive denominator alone cannot establish a usable sample.
The adequacy policy is pending source review. All observed skills must be included
in the export. A profile can additionally include vocabulary skills with zero
counts; absence from the profile is not a claim about a student's ability.

Each posting skill includes the same ID, name, and category as the vocabulary,
count, rate, and up to three evidence samples. The mock generator selects the
first occurrence from each distinct posting, ordered by posting ID. Samples are
illustrative; consumers needing all contexts must read the complete evidence.

## Requirement contexts and evidence

The context enum is `required`, `preferred`, `alternative`,
`explicitly_not_required`, or `unspecified`. Context describes the literal
evidence; it does not change mention counts. A negated Python mention and both
members of “Python or Java” contribute literal mentions, without establishing
mandatory Python and Java requirements.

Alternative members share an `alternative_group_id`, scoped to the posting.
Other contexts require that field to be null. If part of an alternative is
outside the vocabulary, retain known members and flag
`incomplete_alternative_group`. A complete group requires at least two distinct
canonical IDs. The source excerpt preserves whether the group was required or
preferred; v1 does not encode the group's strength separately.

`uncertainty_flags` is an array of descriptive codes, never invented confidence
scores. Empty means no uncertainty was flagged by the rules, not proven
correctness. Proposed context classification should resolve explicit negatives
before positive requirements and preserve alternatives before flattening lists.
Conflicting or ambiguous context should remain unspecified with flags. A full
context classifier is not part of this milestone.

`cleaned_postings_v1.json` is a supporting internal bundle with the same version
and mock fields plus `postings`. It is checked in Python, rather than introducing
a third public JSON Schema in this milestone. Each retained posting carries:

- `posting_id`, `source_id`, original `raw_text`, separate `cleaned_text`;
- independent `classifications`, the `classification_basis`, eligibility and
  analysis booleans, and a nullable `exclusion_reason`;
- complete `skill_evidence`: canonical ID, posting ID, matched text and offsets,
  verbatim excerpt, context, alternative group, and uncertainty flags.

Evidence IDs must refer to retained analyzed postings, exact spans must satisfy
the vocabulary policy, and profile samples must occur in the complete evidence.
Repeated occurrences are retained; exact duplicate evidence records are rejected.
The synthetic text is already plain text, so raw and cleaned text happen to agree.
The future cleaner must decode entities, strip tags while preserving sentence/
list boundaries, and retain technology punctuation; it must not overwrite raw text.

## O*NET is separate

`onet_skills` contains source `element_id`, `name`, `category`, and a `source_id`
referencing an explicitly loaded O*NET release. v1 intentionally omits ratings;
do not insert numeric ratings without adding scale identifiers, names, bounds,
and meaning in a versioned contract update. Source association IDs are unique
within their source. No O*NET ratings enter posting frequency calculations.

O*NET 31.0 was inspected and confirms Software Developers `15-1252.00`. The
mock keeps `onet_code: null` and `onet_skills: []` because it contains no real
source associations. Real export must copy IDs/names/categories from the chosen
release. In 31.0's Software Skills file, `Element ID` identifies a category and
`Workplace Example` names a technology: a category ID is not a unique technology
ID. The minimal v1 `onet_skills` shape is for occupation-to-skill elements; retain
software examples and their category relationships separately until a source
mapping contract is agreed. Do not silently flatten them into this array.

## Consumer handoff

Part 2 loads the vocabulary and records direct evidence with the same IDs and
version. Student corrections preserve the distinction between missing evidence
and missing ability. Part 3 validates the profile and version before comparison,
uses context rather than treating mention rate as requiredness, and displays
missing evidence as “No evidence found in your resume.” Neither consumer should
treat synthetic role coverage as real recommendations. This milestone does not
define their resume payloads, scoring algorithms, or FastAPI endpoints.
