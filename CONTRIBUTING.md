# Contributing

Use Python 3.12 and the pinned `requirements.txt`. Run these checks from the root:

```sh
python -m waypoint_data.validate
python -m unittest discover -s tests -v
```

For source inspection, also install `requirements-inspection.txt` and run
`python scripts/inspect_kaggle.py --help`. It reads preserved CSV input and writes
inspection reports; it does not create production role profiles.

Keep raw downloads unchanged and out of git. Retain source URLs, versions,
checksums, licenses, and original IDs. Never commit authentication credentials.
Inspection outputs may be committed; keep full raw descriptions in the ignored
source directory.

Part 1 owns data preparation, vocabulary, posting evidence, and role exports.
The existing local-model resume interface is a separate starter and is not yet
integrated with these contracts. Coordinate resume extraction, comparison, API,
roadmap, and UI integration across the relevant owners. Coordinate changes to
canonical IDs, matching rules, vocabulary versions, or schemas with all consumers.

Change `vocabulary_version` whenever names, aliases, categories, or matching rules
change. Schema changes need a schema-version decision and fixtures that validate.
Do not silently rename/reuse canonical IDs or infer SQL from PostgreSQL, Java
from JavaScript, or Git from GitHub.

Preserve `is_mock` through consumers. A fixture must never become a real finding
by changing that flag. Never describe this historical snapshot as live market
demand. Keep O*NET associations and scales separate from posting frequencies.

Add regression tests for behavior changes. `tests/fixtures/extraction_cases_v1.json`
is a future extractor acceptance suite, not a claim that extraction has already
been implemented or audited. The current tests cover candidate policy and
contract integrity, including empty inputs, alternatives, negatives, duplicates,
punctuation, overlapping names, and ambiguous aliases.
