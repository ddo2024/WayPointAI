"""Validate JSON contracts and cross-file evidence/count invariants."""

import argparse
import json
import math
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from waypoint_data.matching_policy import is_declared_match

ROOT = Path(__file__).resolve().parents[1]
FORMATS = FormatChecker()


@FORMATS.checks("date-time", raises=(ValueError, TypeError))
def utc_timestamp(value):
    if not isinstance(value, str):
        return True
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", value)) and datetime.fromisoformat(value.replace("Z", "+00:00")).utcoffset().total_seconds() == 0


@FORMATS.checks("date", raises=(ValueError, TypeError))
def calendar_date(value):
    if not isinstance(value, str):
        return True
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)) and bool(date.fromisoformat(value))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_index(records, key, scope):
    result = {}
    for record in records:
        identifier = record[key]
        require(identifier not in result, f"Duplicate {scope} ID: {identifier}")
        result[identifier] = record
    return result


def read_json(path):
    def reject_constant(value):
        raise ValueError(f"Non-JSON numeric constant: {value}")

    def reject_duplicate_keys(pairs):
        document = {}
        for key, value in pairs:
            require(key not in document, f"Duplicate JSON object key: {key}")
            document[key] = value
        return document

    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=reject_constant, object_pairs_hook=reject_duplicate_keys)


def validate_bundle(vocabulary, role, cleaned, schema_dir=ROOT / "schemas"):
    schemas = {}
    for name, document in [("skill_vocabulary", vocabulary), ("role_profile", role)]:
        schema = read_json(Path(schema_dir) / f"{name}_v1.schema.json")
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema, format_checker=FORMATS).validate(document)
        schemas[name] = schema

    require(set(cleaned) == {"schema_version", "vocabulary_version", "is_mock", "postings"}, "Invalid cleaned-postings envelope")
    require(isinstance(cleaned["postings"], list), "postings must be an array")
    require(type(cleaned["is_mock"]) is bool, "cleaned is_mock must be boolean")
    for field in ("schema_version", "vocabulary_version", "is_mock"):
        require(vocabulary[field] == role[field] == cleaned[field], f"Bundle {field} mismatch")
    if role["vocabulary_version"].startswith("mock-"):
        require(role["is_mock"], "Mock vocabulary cannot be presented as real")

    skills = unique_index(vocabulary["skills"], "canonical_id", "vocabulary")
    role_skills = unique_index(role["posting_skills"], "canonical_id", "role skill")
    postings = unique_index(cleaned["postings"], "posting_id", "posting")
    metadata = role["metadata"]
    sources = unique_index(metadata["sources"], "source_id", "source")
    for source in sources.values():
        dates = source["collection_dates"]
        require(dates is None or dates["start"] <= dates["end"], "Reversed collection dates")
        if source["source_type"] == "synthetic" or source["status"] == "synthetic":
            require(role["is_mock"], "Synthetic source cannot be presented as real")
        if source["status"] == "loaded":
            require(source["version"] is not None, "Loaded sources need a release or snapshot identifier")

    aliases = {}
    for skill_id, skill in skills.items():
        candidates = [skill["display_name"], *skill["aliases"]]
        folded = [alias.casefold() for alias in candidates]
        require(len(folded) == len(set(folded)), f"Duplicate alias for {skill_id}")
        for alias in folded:
            require(alias not in aliases, f"Alias collision: {alias}")
            aliases[alias] = skill_id
        contexts = skill["matching_policy"]["context_requirements"]
        unique_index(contexts, "alias", f"context requirement for {skill_id}")
        for context in contexts:
            require(context["alias"] in candidates, f"Context rule alias absent from {skill_id}")
            for pattern in context["any_of_patterns"]:
                re.compile(pattern)

    onet_ids = set()
    for item in role["onet_skills"]:
        key = (item["source_id"], item["element_id"])
        require(key not in onet_ids, f"Duplicate O*NET element: {key}")
        onet_ids.add(key)
        require(item["source_id"] in sources, "Unknown O*NET source")
        source = sources[item["source_id"]]
        require(source["source_type"] == "onet" and source["status"] == "loaded", "O*NET associations require a loaded O*NET source")

    # Reuse the evidence definition from the role schema for complete evidence.
    evidence_validator = Draft202012Validator({
        "$schema": schemas["role_profile"]["$schema"],
        "$ref": "#/$defs/evidence", "$defs": schemas["role_profile"]["$defs"],
    }, format_checker=FORMATS)
    sample_keys = ("posting_id", "excerpt", "requirement_context", "alternative_group_id", "uncertainty_flags")
    mention_postings = defaultdict(set)
    full_samples = defaultdict(list)
    eligible = analyzed = unusable = 0
    for posting_id, record in postings.items():
        require(isinstance(posting_id, str) and bool(posting_id), "Empty posting ID")
        require(record["source_id"] in sources, f"Unknown source for {posting_id}")
        source = sources[record["source_id"]]
        require(source["source_type"] in {"job_postings", "synthetic"} and source["status"] in {"loaded", "synthetic"}, "Posting source must be loaded or synthetic")
        require(isinstance(record["raw_text"], str) and isinstance(record["cleaned_text"], str), "Posting text must be strings")
        require(type(record["eligible"]) is bool and type(record["analyzed"]) is bool, "Posting flags must be boolean")
        require(isinstance(record["skill_evidence"], list), "skill_evidence must be an array")
        if record["eligible"]:
            for dimension in ("occupation", "specialization", "seniority", "geography"):
                require(record["classifications"][dimension] == metadata["filters"][dimension], f"Eligible posting fails {dimension}: {posting_id}")
        require(not record["analyzed"] or record["eligible"], "Analyzed posting must be eligible")
        if record["analyzed"]:
            require(bool(record["cleaned_text"].strip()), "Analyzed posting needs usable text")
            require(record["exclusion_reason"] is None, "Analyzed posting cannot be excluded")
        else:
            require(bool(record["exclusion_reason"]), "Excluded posting needs a reason")
            require(not record["skill_evidence"], "Unanalyzed postings must not contribute evidence")
        if record["eligible"] and not record["analyzed"]:
            require(record["exclusion_reason"] == "unusable_description", "Eligible exclusion must report unusable text")
            unusable += 1
        eligible += record["eligible"]
        analyzed += record["analyzed"]
        seen_spans = set()
        groups = defaultdict(set)
        incomplete_groups = set()
        for item in record["skill_evidence"]:
            require(set(item) == {*sample_keys, "canonical_id", "matched_text", "start", "end"}, "Unexpected complete evidence fields")
            sample = {key: item[key] for key in sample_keys}
            evidence_validator.validate(sample)
            skill_id = item["canonical_id"]
            require(skill_id in skills, f"Unknown evidence skill: {skill_id}")
            require(item["posting_id"] == posting_id, "Evidence posting ID mismatch")
            start, end = item["start"], item["end"]
            require(type(start) is int and type(end) is int and 0 <= start < end <= len(record["cleaned_text"]), "Invalid evidence offsets")
            require(record["cleaned_text"][start:end] == item["matched_text"], "Matched text differs from evidence offsets")
            require(is_declared_match(skills[skill_id], record["cleaned_text"], start, end), f"Evidence violates matching policy for {skill_id}")
            excerpt_covers_span = any(
                match.start() <= start and match.end() >= end
                for match in re.finditer(re.escape(item["excerpt"]), record["cleaned_text"])
            )
            require(excerpt_covers_span, "Excerpt does not cover the matched occurrence")
            span_id = (skill_id, start, end)
            require(span_id not in seen_spans, "Duplicate evidence occurrence")
            seen_spans.add(span_id)
            mention_postings[skill_id].add(posting_id)
            full_samples[skill_id].append(sample)
            if item["alternative_group_id"]:
                groups[item["alternative_group_id"]].add(skill_id)
                if "incomplete_alternative_group" in item["uncertainty_flags"]:
                    incomplete_groups.add(item["alternative_group_id"])
        for group, members in groups.items():
            require(len(members) >= 2 or group in incomplete_groups, f"Alternative group needs two distinct skills or an incomplete_alternative_group flag: {group}")

    require(metadata["eligible_postings_count"] == eligible, "Eligible denominator mismatch")
    require(metadata["analyzed_postings_count"] == analyzed, "Analyzed denominator mismatch")
    require(metadata["excluded_unusable_descriptions_count"] == unusable, "Unusable description count mismatch")
    require(eligible == analyzed + unusable, "Eligible/analyzed partition mismatch")
    require(set(mention_postings) <= set(role_skills), "Role profile omits an observed skill")
    for skill_id, item in role_skills.items():
        require(skill_id in skills, f"Unknown role skill: {skill_id}")
        for field in ("display_name", "category"):
            require(item[field] == skills[skill_id][field], f"Vocabulary {field} mismatch for {skill_id}")
        expected = len(mention_postings[skill_id])
        require(item["mention_count"] <= analyzed, f"Count exceeds denominator: {skill_id}")
        require(item["mention_count"] == expected, f"Count differs from unique posting evidence: {skill_id}")
        rate = item["mention_rate"]
        if analyzed:
            require(rate is not None and math.isfinite(rate) and math.isclose(rate, expected / analyzed, rel_tol=0, abs_tol=1e-12), f"Incorrect rate: {skill_id}")
        else:
            require(rate is None and metadata["data_status"] == "insufficient_data", "Zero denominator requires null rates and insufficient_data")
        require(expected == 0 or bool(item["evidence_sample"]), "Mentioned skills need an evidence sample")
        for sample in item["evidence_sample"]:
            require(sample in full_samples[skill_id], f"Sample is not retained evidence for {skill_id}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/mock")
    parser.add_argument("--schema-dir", type=Path, default=ROOT / "schemas")
    args = parser.parse_args()
    documents = [read_json(args.data_dir / f"{name}_v1.json") for name in ("skill_vocabulary", "role_profile", "cleaned_postings")]
    validate_bundle(*documents, schema_dir=args.schema_dir)
    print("PASS: schemas, versions, unique IDs, evidence references, counts, rates and mock labels")


if __name__ == "__main__":
    main()
