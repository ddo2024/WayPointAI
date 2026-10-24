# Kaggle snapshot inspection

This Markdown report records the initial inspected snapshot. `python3 scripts/inspect_kaggle.py` regenerates the JSON inspection report and pending audit sample; it does not overwrite these notes. Consult `kaggle_inspection.json` for the latest regenerated values and the preserved acquisition manifest for download provenance.

Downloaded **version 3** of [asaniczka's LinkedIn Software Engineering Jobs Dataset](https://www.kaggle.com/datasets/asaniczka/software-engineer-job-postings-linkedin). The official metadata gives a version publication timestamp of **2024-01-27T13:45:21.117Z** and the license name **ODC Attribution License (ODC-By)**. Creator attribution: **asaniczka**. Full provenance, file checksums, exact rules, and representative row metadata are in `kaggle_inspection.json`; description text stays in the ignored raw dataset and is not copied into reports.

The preserved archive is `data/raw/kaggle/software-engineer-job-postings-linkedin-v3.zip`; its unmodified CSV is `data/raw/kaggle/v3/postings.csv`. The ZIP is 11,201,787 bytes and the CSV is 41,704,606 bytes. No authentication was needed.

## Observed data

The CSV contains **9,380 rows and 11 columns**:

`job_title`, `company`, `job_location`, `job_link`, `first_seen`, `search_city`, `search_country`, `job level`, `job_type`, `job_summary`, `job_skills`.

- **4** rows have no `job_summary`; these four URLs point to LinkedIn search pages instead of individual postings.
- **13** rows have no `job_skills`. That field is source-provided extraction, not verified direct evidence. Extract from `job_summary` using the shared vocabulary instead.
- Every `first_seen` value is **2023-12-25**. Its exact meaning has not been independently verified. The collection window remains unknown; the download date and version publication date are separate.
- Source `job level` values are **Mid senior: 8,101**, **Associate: 1,279**. There is no explicit entry-level category. **395** Associate rows contain a non-entry title cue, and **63** Mid senior rows contain an entry title cue. These are screening conflicts, not verified ground-truth labels.
- Exact rows and exact `job_link` strings are unique. Parsing numeric LinkedIn IDs finds **one excess duplicate row** under different URL slugs. A proposed normalized company/title/location/summary diagnostic finds **133 excess matches**; those matches have not been removed or adopted as a production deduplication rule.

## Requested scope

A conservative title/location screen found **one candidate** with all of these cues:

1. `software engineer` or `software developer` in the title.
2. `backend`, `back-end`, or `back end` in the title.
3. An explicit entry/junior/new-graduate/graduate/beginning title cue, without a senior/staff/lead/manager/director/principal/architect cue.
4. An explicit U.S. location (United States or a U.S. state/DC abbreviation), without an explicit conflicting country.
5. A parseable posting ID and nonblank summary.

That candidate is **Beginning Software Engineer (Back End)** in **Annapolis Junction, MD**, LinkedIn ID **3784448460**. Its description requires **TS/SCI clearance with polygraph**. This is not a sufficient basis for a general-student role profile. The degree-or-experience alternative in its description also needs careful context handling.

This is **not a final eligible-posting count**. Generic titles, metropolitan-area locations, and backend or junior evidence appearing only in descriptions remain unclassified. The screen leaves 3,809 titles without either seniority cue and 361 locations without a recognized country cue. `Associate` is not mapped to entry level, and `search_country` is not substituted for actual job geography. No scope filters were broadened.

## Next inspection and implementation decisions

Use the report's recorded rules and examples to define a description-aware classification policy. Explicitly decide how to handle zero-to-two years of experience, internships, degree-versus-experience alternatives, remote eligibility, and uncertain/conflicting evidence. Audit ambiguous cases before setting a minimum usable-sample threshold or publishing frequencies. Preserve raw input, log any exclusions and duplicates, and re-extract skills with the shared vocabulary.

No skill-frequency computation, parser accuracy audit, final role classification, or source-specific ingestion pipeline was performed in this inspection. The snapshot represents historical scraped postings, not live market demand.
