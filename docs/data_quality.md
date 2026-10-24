# Source inspection and data quality

This milestone provides contracts and mocks plus actual source acquisition and
inspection. It does not claim that a production cleaning, classification,
extraction, or aggregation pipeline has run.

## Decisions and blockers

There is no contradiction preventing mock integration. The original README's
“resumes of successful people” product description conflicted with the supplied
brief and has been replaced with own-resume evidence and coverage.

The source-file blocker was resolved by downloading Kaggle v3 and O*NET 31.0.
The remaining consequential decisions apply to **real profile publication**:

- Decide entry-level criteria after description review: explicit junior/new-grad
  titles, acceptable experience requirements, degree/experience alternatives,
  and whether internships belong in a separate profile. Do not equate Associate
  with entry-level or Software Developers with backend.
- Define remote U.S. eligibility and handling of vague metro locations using
  explicit location/description evidence. Search geography is not job geography.
- Choose a minimum usable sample policy and explain representativeness limits.
  No arbitrary threshold or silent filter expansion has been applied.
- Review source-derived skill mappings and aliases. Mock canonical IDs are
  project vocabulary examples, not invented O*NET relationships.

Unknown or conflicting classifications will be retained and excluded from the
strict profile, with reasons. Keep the requested U.S. / backend / entry-level
scope until its actual usable sample has been reported.

## Observed source quality

The [Kaggle report](../data/inspection/kaggle_inspection.json) records actual
headers, inferred types, nulls, date values, representative records, diagnostic
patterns, and counts. There are 9,380 rows and 11 columns. `job_summary` is present
in 9,376 rows; four missing summaries correspond to search-page links rather
than valid posting URLs. `job_skills` is missing in 13 rows and is not treated as
validated extraction or direct requirement evidence.

All `first_seen` values are `2023-12-25`; this does not establish a collection
window. Snapshot v3 was published January 27, 2024. Download timestamps record
acquisition only. This is a historical sample, not live market demand.

Exact URL strings are unique, but parsing numeric LinkedIn job IDs reveals one
excess duplicate row. A separate normalized company/title/location/summary
diagnostic finds 133 excess matches; these are candidates for review, not 133
approved removals. The two diagnostics overlap and must not be added together.
**No source records have been removed.** Raw downloads are unchanged.

Only `Associate` (1,279) and `Mid senior` (8,101) appear as source levels. There
are 395 Associate records with senior-type title cues and 63 Mid senior records
with entry cues. The conservative inspection screen preserves 3,809 unknown
seniority titles, five conflicting title classifications, and 361 unknown
geographies. These are inspection diagnostics, not final classification outcomes.

The documented title/location screen finds **one candidate** meeting positive
U.S., backend, and entry title cues, with nonblank text. It requires security
clearance. This does not establish that the dataset has only one qualifying
posting: generic titles and description-only cues remain unresolved. There is
not yet evidence for a sufficiently representative profile. Final eligible and
analyzed counts and real skill frequencies remain unpublished.

The [O*NET report](../data/inspection/onet_inspection.json) records seven actual
CSV files and source-reference checks. Software Developers `15-1252.00` has 10
Essential Skill and 25 Transferable Skill elements, 430 distinct software
examples across 67 categories, and 17 tasks in this release. These occupation
associations do not identify entry-level/backend requirements. Importance uses
scale IM (1–5); Level uses LV (0–7). Ratings remain in the source inspection and
are not combined with posting frequencies.

O*NET's current files include `essential_skills.csv`,
`transferable_skills.csv`, and `software_skills.csv`; adapters must follow this
release's actual headers, not assume older file names. Source element/category
relationships and rating scales were checked against the downloaded references.

## Mock quality

The separate `data/mock/` bundle has eight retained **synthetic** postings: six
eligible, five analyzed, one eligible with unusable text, one seniority mismatch,
and one unknown geography. One analyzed posting has no detected skill and remains
in the denominator. Python has four evidence occurrences across three analyzed
postings, so its literal mention rate is `3 / 5 = 0.6`. Its required, alternative,
and explicitly-not-required contexts remain separate. No claim of real demand
or sample adequacy follows from these numbers.

The executable checks validate schemas, versions, mock labels, canonical IDs,
aliases, evidence references/spans, count arithmetic, and zero-denominator
behavior. Candidate policy tests cover ambiguous Go/R/C, PG, overlapping names,
punctuation, and safe aliases. The generator uses hand-authored evidence; passing
these checks is not a completed real extraction audit. Negation/alternative
classification acceptance cases are supplied for the future extractor.

## Next pipeline work

1. Review the reproducible pending audit sample, including generic titles,
   seniority conflicts, unknown locations, ambiguous terms, and no-obvious-skill
   text. Record human skill labels before comparing parser output, so both false
   positives and missed skills can be measured. All audit outcome fields remain
   null/pending until someone performs that review.
2. Freeze a versioned classification configuration based on that evidence.
   Preserve unknown and conflict states separately for each dimension.
3. Implement source adapters using the verified headers. Keep raw text separate;
   decode HTML entities and preserve useful paragraph/list boundaries and C++,
   C#, .NET, and Node.js punctuation. A description is not usable merely because
   it is nonblank: detect navigation/boilerplate-only text and report exclusions.
4. Deduplicate in a documented sequence: canonical source ID first; then an exact
   normalized company/title/location/cleaned-description key when an ID is
   unavailable. Do not merge different valid source IDs by fuzzy similarity.
   Preserve every original row's link to its retained representative. Prefer
   usable text, then a stable content hash and original row ordinal as tie-breaks.
   Record removal counts for each step, and flag conflicting source-ID records.
   The observed 133 fallback-like matches are diagnostics, not instructions to
   remove them all.
5. Run classification and report eligible, unusable, and analyzed counts before
   broadening filters. Then implement extraction/context rules, review false
   positives and missed skills, and aggregate distinct posting IDs. Export only
   validated bundles with complete evidence and declared sample limitations.

Proposed future modules are `inspect.py`, `clean.py`, `deduplicate.py`,
`classify.py`, `extract.py`, `aggregate.py`, and `export.py`, sharing the existing
matching-policy and validation code. Paths and filter rules should be explicit
CLI/config inputs. No NLP dependency is justified yet.

## Attribution

Source: **O*NET® 31.0 Database**, U.S. Department of Labor, Employment and Training
Administration, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Original downloads are unmodified; inspection summaries and counts are
project-generated derivatives. See [official attribution guidance](https://www.onetcenter.org/license_db.html).

Source: **asaniczka, LinkedIn Software Engineering Jobs Dataset, Kaggle v3**,
[source page](https://www.kaggle.com/datasets/asaniczka/software-engineer-job-postings-linkedin).
The official API metadata identifies ODC Attribution License (ODC-By). Preserve
the creator, dataset URL, version, and original metadata with any derived exports.
