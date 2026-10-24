"""Shared candidate validation only; not a skill extractor or context classifier."""

import re


def is_declared_match(skill: dict, text: str, start: int, end: int) -> bool:
    """Check a specific character span against technology_token_v1 and alias rules.

    Offsets are Python Unicode character offsets in cleaned text. Context regexes
    must cover this occurrence, not a different mention elsewhere in the text.
    """
    policy = skill["matching_policy"]
    flags = 0 if policy["case_sensitive"] else re.IGNORECASE
    for alias in [skill["display_name"], *skill["aliases"]]:
        pattern = re.compile(r"(?<![\w+#.])" + re.escape(alias) + r"(?![\w+#]|\.\w)", flags)
        candidate = pattern.match(text, start)
        if candidate is None or candidate.end() != end:
            continue
        requirements = [rule for rule in policy["context_requirements"] if rule["alias"] == alias]
        if all(any(
            match.start() <= start and match.end() >= end
            for expression in rule["any_of_patterns"]
            for match in re.finditer(expression, text, flags)
        ) for rule in requirements):
            return True
    return False
