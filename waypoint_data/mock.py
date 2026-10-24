"""Generate hand-authored synthetic fixtures; this is NOT a posting extractor."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1.0.0"
VOCABULARY_VERSION = "mock-1.0.0"


def build_bundle(generated_at: str) -> tuple[dict, dict, dict]:
    definitions = [
        ("aws", "AWS", "cloud_platform", ["Amazon Web Services"]),
        ("c", "C", "programming_language", []),
        ("c_plus_plus", "C++", "programming_language", []),
        ("c_sharp", "C#", "programming_language", []),
        ("dotnet", ".NET", "framework", []),
        ("git", "Git", "version_control", []),
        ("github", "GitHub", "developer_platform", []),
        ("go", "Go", "programming_language", ["Golang"]),
        ("java", "Java", "programming_language", []),
        ("javascript", "JavaScript", "programming_language", []),
        ("nodejs", "Node.js", "runtime", []),
        ("postgresql", "PostgreSQL", "database", ["Postgres"]),
        ("python", "Python", "programming_language", []),
        ("r", "R", "programming_language", []),
        ("scikit_learn", "scikit-learn", "machine_learning_library", ["sklearn"]),
        ("sql", "SQL", "query_language", []),
    ]
    skills = []
    for slug, name, category, aliases in definitions:
        requirements = []
        if slug in {"go", "r", "c"}:
            requirements = [{
                "alias": name,
                "any_of_patterns": [
                    rf"(?<![A-Za-z0-9_+#.]){name}\s+(?:programming|language|developer)(?![A-Za-z0-9_])"
                ],
            }]
        skills.append({
            "canonical_id": f"skill:{slug}", "display_name": name,
            "category": category, "aliases": aliases,
            "matching_policy": {
                "case_sensitive": slug in {"r", "c"},
                "boundary": "technology_token_v1", "overlap": "longest_match_first",
                "context_requirements": requirements,
            },
        })
    vocabulary = {
        "schema_version": VERSION, "vocabulary_version": VOCABULARY_VERSION,
        "is_mock": True, "skills": skills,
    }

    def posting(number, text, *, eligible=True, exclusion=None, seniority="entry_level", geography="US"):
        return {
            "posting_id": f"mock-{number:03d}", "source_id": "synthetic-fixture",
            "raw_text": text, "cleaned_text": text,
            "classifications": {
                "occupation": "software_developer", "specialization": "backend",
                "seniority": seniority, "geography": geography,
            },
            "classification_basis": "hand_assigned_synthetic_fixture",
            "eligible": eligible, "analyzed": eligible and bool(text.strip()),
            "exclusion_reason": exclusion,
            "skill_evidence": [],
        }

    postings = [
        posting(1, "Required: Python and PostgreSQL.\nUse Python daily.\nPreferred: AWS."),
        posting(2, "Required: Python or Java.\nPreferred: Git and GitHub."),
        posting(3, "No Python experience required.\nRequired: C++ and C#.\nPreferred: .NET and Node.js."),
        posting(4, "Required: JavaScript and SQL.\nPreferred: Golang, R programming, and C programming."),
        posting(5, "Work with kind colleagues. Be curious and communicate clearly."),
        posting(6, "", exclusion="unusable_description"),
        posting(7, "Required: Python.", eligible=False, exclusion="seniority_mismatch", seniority="senior"),
        posting(8, "Required: Python.", eligible=False, exclusion="geography_unknown", geography=None),
    ]

    def evidence(number, slug, matched, excerpt, context, group=None):
        record = postings[number - 1]
        start = record["cleaned_text"].index(excerpt) + excerpt.index(matched)
        record["skill_evidence"].append({
            "canonical_id": f"skill:{slug}", "posting_id": record["posting_id"],
            "matched_text": matched, "start": start, "end": start + len(matched),
            "excerpt": excerpt, "requirement_context": context,
            "alternative_group_id": group, "uncertainty_flags": [],
        })

    evidence(1, "python", "Python", "Required: Python and PostgreSQL.", "required")
    evidence(1, "python", "Python", "Use Python daily.", "unspecified")
    evidence(1, "postgresql", "PostgreSQL", "Required: Python and PostgreSQL.", "required")
    evidence(1, "aws", "AWS", "Preferred: AWS.", "preferred")
    evidence(2, "python", "Python", "Required: Python or Java.", "alternative", "mock-002:alt-1")
    evidence(2, "java", "Java", "Required: Python or Java.", "alternative", "mock-002:alt-1")
    evidence(2, "git", "Git", "Preferred: Git and GitHub.", "preferred")
    evidence(2, "github", "GitHub", "Preferred: Git and GitHub.", "preferred")
    evidence(3, "python", "Python", "No Python experience required.", "explicitly_not_required")
    evidence(3, "c_plus_plus", "C++", "Required: C++ and C#.", "required")
    evidence(3, "c_sharp", "C#", "Required: C++ and C#.", "required")
    evidence(3, "dotnet", ".NET", "Preferred: .NET and Node.js.", "preferred")
    evidence(3, "nodejs", "Node.js", "Preferred: .NET and Node.js.", "preferred")
    evidence(4, "javascript", "JavaScript", "Required: JavaScript and SQL.", "required")
    evidence(4, "sql", "SQL", "Required: JavaScript and SQL.", "required")
    evidence(4, "go", "Golang", "Preferred: Golang, R programming, and C programming.", "preferred")
    evidence(4, "r", "R", "Preferred: Golang, R programming, and C programming.", "preferred")
    evidence(4, "c", "C", "Preferred: Golang, R programming, and C programming.", "preferred")
    for record in postings:
        record["skill_evidence"].sort(key=lambda item: (item["start"], item["canonical_id"]))
    cleaned = {
        "schema_version": VERSION, "vocabulary_version": VOCABULARY_VERSION,
        "is_mock": True, "postings": postings,
    }
    analyzed = sum(record["analyzed"] for record in postings)
    posting_skills = []
    sample_keys = ("posting_id", "excerpt", "requirement_context", "alternative_group_id", "uncertainty_flags")
    for skill in skills:
        mentions = [
            item for record in postings if record["analyzed"]
            for item in record["skill_evidence"] if item["canonical_id"] == skill["canonical_id"]
        ]
        per_posting = {}
        for item in mentions:
            per_posting.setdefault(item["posting_id"], item)
        count = len(per_posting)
        posting_skills.append({
            **{key: skill[key] for key in ("canonical_id", "display_name", "category")},
            "mention_count": count, "mention_rate": count / analyzed if analyzed else None,
            "evidence_sample": [{key: item[key] for key in sample_keys} for item in list(per_posting.values())[:3]],
        })
    role = {
        "schema_version": VERSION, "vocabulary_version": VOCABULARY_VERSION, "is_mock": True,
        "role_id": "backend_entry_us", "display_title": "Entry-level backend software engineering (US) — MOCK",
        "onet_code": None,
        "metadata": {
            "filters": {
                "occupation": "software_developer", "specialization": "backend",
                "seniority": "entry_level", "geography": "US", "rules_version": "mock-assignment-1.0.0",
                "unknown_policy": "exclude_and_report", "conflict_policy": "exclude_and_report",
            },
            "sources": [{
                "source_id": "synthetic-fixture", "source_type": "synthetic", "uri": None,
                "version": VOCABULARY_VERSION, "collection_dates": None, "status": "synthetic",
            }],
            "generated_at": generated_at, "eligible_postings_count": 6,
            "analyzed_postings_count": analyzed, "excluded_unusable_descriptions_count": 1,
            "data_status": "unassessed",
            "limitations": [
                "MOCK ONLY: all postings, classifications, evidence and frequencies are synthetic integration examples.",
                "No O*NET associations or downloaded posting observations contribute to this fixture.",
                "Mention frequency includes alternatives and explicit negatives; it is not mandatory-requirement frequency.",
                "The vocabulary is illustrative, incomplete, and not a source-derived role recommendation.",
                "A real sample adequacy threshold has not been selected."
            ],
        },
        "onet_skills": [], "posting_skills": posting_skills,
    }
    return vocabulary, role, cleaned


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/mock"))
    parser.add_argument("--generated-at", default=None, help="UTC ISO timestamp ending Z; reuse for byte-identical regeneration")
    args = parser.parse_args()
    timestamp = args.generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    vocabulary, role, cleaned = build_bundle(timestamp)
    from waypoint_data.validate import validate_bundle
    validate_bundle(vocabulary, role, cleaned)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, document in [("skill_vocabulary_v1", vocabulary), ("role_profile_v1", role), ("cleaned_postings_v1", cleaned)]:
        (args.output_dir / f"{name}.json").write_text(json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote and validated synthetic fixtures to {args.output_dir}")


if __name__ == "__main__":
    main()
