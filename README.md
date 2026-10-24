# WayPointAI
WayPointAI is a career-advice application. Its existing Streamlit interface
analyzes resume text against selected target roles using a model that runs locally.
The interface is not yet integrated with the role-profile data contracts below.

The data-contract work in this repository defines two JSON Schemas, shared mock
fixtures, a candidate-matching policy, and validation. It also contains inspection
reports from downloaded public sources. The contracts are not yet wired into the
resume interface or a production roadmap generator.

## Start here

- [Skill vocabulary schema](schemas/skill_vocabulary_v1.schema.json) and [role profile schema](schemas/role_profile_v1.schema.json)
- [Mock skill vocabulary](data/mock/skill_vocabulary_v1.json) and [mock role profile](data/mock/role_profile_v1.json)
- [Complete mock posting evidence](data/mock/cleaned_postings_v1.json)
- [Contracts and matching semantics](docs/contracts.md)
- [Data quality, open decisions, and next implementation steps](docs/data_quality.md)

Every mock artifact has `is_mock: true` and vocabulary version `mock-1.0.0`.
Its counts are synthetic examples, not findings about jobs. Parts 2 and 3 can
load these fixtures now; both must use the same vocabulary version and canonical IDs.

## Run locally

Use Python 3.12 from the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m waypoint_data.validate
python -m unittest discover -s tests -v
```

## Run the web interface

Install the dependencies above, then start Streamlit:

```sh
streamlit run app.py
```

The interface accepts PDF or UTF-8 text resumes and target job titles. It uses
the public `AnusmitaRC21/smolified-resume-analyzer` 270M-parameter Gemma 3 model.
The model is downloaded from Hugging Face on first use and cached; an internet
connection and enough disk space are needed for that first analysis. No provider
API key is required. Resume text is processed locally. The app analyzes up to
18,000 characters per request; scanned PDFs without selectable text are not
supported.

Regenerate the mocks with `python -m waypoint_data.mock`. It validates before
writing. To reproduce exactly, pass `--generated-at` with the existing profile's
`metadata.generated_at`. `--output-dir` and validation's `--data-dir` /
`--schema-dir` accept other paths.

## Downloaded sources

The requested downloads are already present locally; raw files are git-ignored.

| Source | Local location | Inspected result |
| --- | --- | --- |
| O*NET 31.0 | `data/raw/onet/31.0/` | Seven official CSVs, provenance, checksums, and documentation |
| Kaggle snapshot v3 | `data/raw/kaggle/v3/postings.csv` | 9,380 rows; descriptions available; 4 missing summaries |

See the [O*NET inspection](data/inspection/onet_inspection.json) and
[Kaggle inspection](data/inspection/kaggle_inspection.md). Source URLs, acquisition
times, release identifiers, license attribution, and SHA-256 hashes are recorded
in the reports. Acquisition and release dates are separate from collection dates.

Conservative title/location screening found **one** U.S. entry-level backend
candidate. This is an initial screen, not a final eligible-posting count: generic
titles and description-only evidence remain unclassified. The scope has not been
broadened, and no real posting skill frequencies have been published.

## Structure

```text
schemas/                 # Two versioned integration contracts
data/mock/               # Synthetic vocabulary, profile, complete evidence
data/raw/                # Original downloaded sources (ignored by git)
data/inspection/         # Actual source reports and pending audit sample
waypoint_data/           # Mock generator, candidate policy, bundle validator
scripts/                 # Reproducible source inspection
tests/                   # Executable contract tests and future extraction cases
docs/                    # Integration semantics, decisions, quality report
```

Next, add `inspect → clean → deduplicate → classify → extract → aggregate → export`
modules under `waypoint_data/` after reviewing the sampled descriptions and fixing
the classification rules. A real source adapter and end-to-end extractor are not
implemented in this milestone.
