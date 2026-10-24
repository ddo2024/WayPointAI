import copy
import tempfile
import unittest
from pathlib import Path

from jsonschema import ValidationError

from waypoint_data.mock import build_bundle
from waypoint_data.matching_policy import is_declared_match
from waypoint_data.validate import read_json, validate_bundle


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.vocabulary, self.role, self.cleaned = build_bundle("2026-10-24T00:31:08Z")

    def validate(self):
        validate_bundle(self.vocabulary, self.role, self.cleaned)

    def rejected(self):
        with self.assertRaises((ValueError, ValidationError)):
            self.validate()

    def test_committed_fixtures_validate(self):
        root = Path(__file__).resolve().parents[1] / "data/mock"
        validate_bundle(*(read_json(root / f"{name}_v1.json") for name in ("skill_vocabulary", "role_profile", "cleaned_postings")))

    def test_literal_frequency_includes_negative_and_alternative(self):
        self.validate()
        python = next(item for item in self.role["posting_skills"] if item["canonical_id"] == "skill:python")
        self.assertEqual(python["mention_count"], 3)  # Four occurrences, three distinct postings.
        self.assertEqual(python["mention_rate"], 0.6)
        self.assertEqual({item["requirement_context"] for item in python["evidence_sample"]}, {"required", "alternative", "explicitly_not_required"})
        self.assertTrue(self.cleaned["postings"][4]["analyzed"])
        self.assertEqual(self.cleaned["postings"][4]["skill_evidence"], [])
        self.assertEqual(self.role["metadata"]["analyzed_postings_count"], 5)

    def test_duplicate_vocabulary_id(self):
        duplicate = copy.deepcopy(self.vocabulary["skills"][0])
        duplicate["display_name"] = "Different name, same ID"
        self.vocabulary["skills"].append(duplicate)
        self.rejected()

    def test_duplicate_posting_id(self):
        self.cleaned["postings"].append(copy.deepcopy(self.cleaned["postings"][0]))
        self.rejected()

    def test_duplicate_role_skill_id(self):
        self.role["posting_skills"].append(copy.deepcopy(self.role["posting_skills"][0]))
        self.rejected()

    def test_wrong_vocabulary_version(self):
        self.role["vocabulary_version"] = "other"
        self.rejected()

    def test_mock_cannot_be_relabeled_real(self):
        for document in (self.role, self.vocabulary, self.cleaned):
            document["is_mock"] = False
        self.rejected()

    def test_unknown_role_id(self):
        self.role["posting_skills"][0]["canonical_id"] = "skill:invented"
        self.rejected()

    def test_unknown_evidence_id(self):
        self.cleaned["postings"][0]["skill_evidence"][0]["canonical_id"] = "skill:invented"
        self.rejected()

    def test_invalid_evidence_reference(self):
        self.role["posting_skills"][0]["evidence_sample"][0]["posting_id"] = "missing-posting"
        self.rejected()

    def test_wrong_display_name(self):
        self.role["posting_skills"][0]["display_name"] = "Wrong name"
        self.rejected()

    def test_repeated_occurrence_is_not_an_extra_posting(self):
        item = next(item for item in self.role["posting_skills"] if item["canonical_id"] == "skill:python")
        item["mention_count"] = 4
        item["mention_rate"] = 0.8
        self.rejected()

    def test_wrong_rate(self):
        self.role["posting_skills"][0]["mention_rate"] = 0.9
        self.rejected()

    def test_wrong_denominator(self):
        self.role["metadata"]["analyzed_postings_count"] = 4
        self.rejected()

    def test_unusable_description_count(self):
        self.role["metadata"]["excluded_unusable_descriptions_count"] = 0
        self.rejected()

    def test_zero_denominator(self):
        self.cleaned["postings"] = []
        self.role["metadata"].update(eligible_postings_count=0, analyzed_postings_count=0, excluded_unusable_descriptions_count=0, data_status="insufficient_data")
        for item in self.role["posting_skills"]:
            item.update(mention_count=0, mention_rate=None, evidence_sample=[])
        self.validate()
        self.role["posting_skills"][0]["mention_rate"] = 0.0
        self.rejected()

    def test_zero_denominator_requires_insufficient_status_even_with_no_skills(self):
        self.vocabulary["skills"] = []
        self.role["posting_skills"] = []
        self.cleaned["postings"] = []
        self.role["metadata"].update(eligible_postings_count=0, analyzed_postings_count=0, excluded_unusable_descriptions_count=0, data_status="insufficient_data")
        self.validate()
        self.role["metadata"]["data_status"] = "usable_sample"
        self.rejected()

    def test_alternative_relation_requires_group(self):
        item = self.cleaned["postings"][1]["skill_evidence"][0]
        item["alternative_group_id"] = None
        self.rejected()

    def test_incomplete_alternative_requires_explicit_flag(self):
        record = self.cleaned["postings"][1]
        record["skill_evidence"] = [item for item in record["skill_evidence"] if item["canonical_id"] != "skill:java"]
        java = next(item for item in self.role["posting_skills"] if item["canonical_id"] == "skill:java")
        java.update(mention_count=0, mention_rate=0.0, evidence_sample=[])
        self.rejected()
        alternative = next(item for item in record["skill_evidence"] if item["canonical_id"] == "skill:python")
        alternative["uncertainty_flags"] = ["incomplete_alternative_group"]
        python = next(item for item in self.role["posting_skills"] if item["canonical_id"] == "skill:python")
        for sample in python["evidence_sample"]:
            if sample["posting_id"] == record["posting_id"]:
                sample["uncertainty_flags"] = ["incomplete_alternative_group"]
        self.validate()

    def test_excerpt_must_cover_same_occurrence(self):
        self.cleaned["postings"][0]["skill_evidence"][0]["excerpt"] = "Use Python daily."
        self.rejected()

    def test_punctuation_in_evidence_preserved(self):
        self.validate()
        self.assertEqual({item["matched_text"] for item in self.cleaned["postings"][2]["skill_evidence"]}, {"Python", "C++", "C#", ".NET", "Node.js"})

    def test_corrupt_span(self):
        self.cleaned["postings"][0]["skill_evidence"][0]["end"] += 1
        self.rejected()

    def test_unrelated_alias_cannot_support_a_skill(self):
        record = self.cleaned["postings"][0]
        item = record["skill_evidence"][0]
        item.update(start=record["cleaned_text"].index("AWS"), end=record["cleaned_text"].index("AWS") + 3, matched_text="AWS", excerpt="Preferred: AWS.")
        self.rejected()

    def test_candidate_matching_rules(self):
        skills = {item["canonical_id"]: item for item in self.vocabulary["skills"]}
        cases = [
            ("We go to the office.", "go", "go", False),
            ("We go to the office. Go programming is useful.", "go", "go", False),
            ("Go programming", "Go", "go", True),
            ("Golang", "Golang", "go", True),
            ("R&D", "R", "r", False),
            ("Grade C", "C", "c", False),
            ("R programming", "R", "r", True),
            ("C programming", "C", "c", True),
            ("JavaScript", "Java", "java", False),
            ("GitHub", "Git", "git", False),
            ("PostgreSQL", "SQL", "sql", False),
            ("C++", "C", "c", False),
            ("C++", "C++", "c_plus_plus", True),
            ("C#", "C#", "c_sharp", True),
            (".NET", ".NET", "dotnet", True),
            ("Node.js", "Node.js", "nodejs", True),
            ("Postgres", "Postgres", "postgresql", True),
            ("PG", "PG", "postgresql", False),
            ("Amazon Web Services", "Amazon Web Services", "aws", True),
            ("sklearn", "sklearn", "scikit_learn", True),
            ("Python.", "Python", "python", True),
        ]
        for text, matched, slug, expected in cases:
            with self.subTest(text=text, skill=slug):
                start = text.index(matched)
                self.assertEqual(is_declared_match(skills[f"skill:{slug}"], text, start, start + len(matched)), expected)

    def test_alias_collision(self):
        self.vocabulary["skills"][0]["aliases"].append("JavaScript")
        self.rejected()

    def test_missing_observed_skill(self):
        self.role["posting_skills"] = [item for item in self.role["posting_skills"] if item["canonical_id"] != "skill:python"]
        self.rejected()

    def test_invalid_date(self):
        self.role["metadata"]["generated_at"] = "2026-02-30T00:00:00Z"
        self.rejected()

    def test_deterministic_generation(self):
        self.assertEqual((self.vocabulary, self.role, self.cleaned), build_bundle("2026-10-24T00:31:08Z"))

    def test_json_loader_rejects_duplicate_keys_and_nonfinite_numbers(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid.json"
            for text in ['{"a": 1, "a": 2}', '{"a": NaN}']:
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    read_json(path)


if __name__ == "__main__":
    unittest.main()
