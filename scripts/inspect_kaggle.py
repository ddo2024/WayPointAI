"""Inspect the observed Kaggle CSV schema and prepare a pending human audit.

This preserves raw files. It does not implement ingestion, classification,
skill extraction, or a completed manual audit. Run with --help for paths.
"""

from pathlib import Path
from urllib.parse import urlsplit
from datetime import datetime, timezone
import argparse
import hashlib, json, re, unicodedata
import pandas as pd

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--input', type=Path, default=root/'data/raw/kaggle/v3/postings.csv', help='Downloaded Kaggle postings.csv (observed schema only).')
parser.add_argument('--output-dir', type=Path, default=root/'data/inspection', help='Directory for inspection and pending audit JSON files.')
parser.add_argument('--metadata', type=Path, help='Official metadata JSON; defaults to INPUT parent/../dataset_metadata.json.')
parser.add_argument('--archive', type=Path, help='Preserved source ZIP; defaults to INPUT parent/../software-engineer-job-postings-linkedin-vVERSION.zip.')
parser.add_argument('--provenance', type=Path, help='Acquisition manifest; defaults to INPUT parent/../download_provenance.json. Missing manifest leaves downloaded_at null.')
parser.add_argument('--generated-at', help='Optional UTC ISO timestamp to reproduce byte-identical reports; defaults to current UTC time.')
args=parser.parse_args()
csv_path=args.input.resolve()
raw=csv_path.parent.parent
metadata_path=(args.metadata or raw/'dataset_metadata.json').resolve()
metadata=json.loads(metadata_path.read_text())
version=metadata['currentVersionNumber']
zip_path=(args.archive or raw/f'software-engineer-job-postings-linkedin-v{version}.zip').resolve()
provenance_path=(args.provenance or raw/'download_provenance.json').resolve()
downloaded_at=None
download_provenance_note='Acquisition manifest unavailable; download timestamp is unknown. Filesystem modification times are not acquisition evidence.'
if provenance_path.exists():
    acquisition=json.loads(provenance_path.read_text())
    archive_hash=hashlib.sha256(zip_path.read_bytes()).hexdigest()
    if acquisition.get('archive',{}).get('sha256')!=archive_hash:
        parser.error('Acquisition manifest archive SHA-256 does not match the selected ZIP; refusing to use its provenance.')
    if acquisition.get('version')!=version or acquisition.get('source_id')!=f'kaggle:{metadata["ref"]}':
        parser.error('Acquisition manifest source/version does not match the selected dataset metadata.')
    downloaded_at=acquisition.get('downloaded_at')
    if downloaded_at is not None:
        try:
            parsed_downloaded_at=datetime.fromisoformat(downloaded_at.replace('Z','+00:00'))
            if 'T' not in downloaded_at or parsed_downloaded_at.tzinfo is None:
                raise ValueError('Acquisition timestamp must include time and timezone')
        except (ValueError,TypeError,AttributeError):
            parser.error('Acquisition manifest downloaded_at must be an ISO timestamp with timezone or null.')
    download_provenance_note='Acquisition timestamp read from the preserved manifest after verifying its archive SHA-256 and source/version. It is not inferred from filesystem timestamps.'
out_dir=args.output_dir.resolve()
out_dir.mkdir(parents=True, exist_ok=True)
generated_at=args.generated_at or datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
if not generated_at.endswith('Z'):
    parser.error('--generated-at must be a UTC ISO timestamp ending in Z')
try:
    datetime.fromisoformat(generated_at.replace('Z','+00:00'))
except ValueError:
    parser.error('--generated-at must be a valid UTC ISO timestamp')
df=pd.read_csv(csv_path)
expected_columns=['job_title','company','job_location','job_link','first_seen','search_city','search_country','job level','job_type','job_summary','job_skills']
if list(df.columns)!=expected_columns:
    parser.error('CSV columns differ from the inspected Kaggle schema; inspect and review the adapter before using this script.')
s=df.fillna('').astype(str)
source_ids=s['job_link'].map(lambda value: (re.search(r'(\d+)$',urlsplit(value).path.rstrip('/')) if '/jobs/view/' in urlsplit(value).path else None)).map(lambda match: match.group(1) if match else None)
backend_pattern=r'\bback[ -]?end\b'
entry_pattern=r'\b(?:entry[ -]?level|junior|jr\.?|new[ -]?grad(?:uate)?|graduate|beginning)\b'
nonentry_pattern=r'\b(?:senior|sr\.?|staff|principal|lead|manager|director|architect)\b'
occupation_pattern=r'\bsoftware\s+(?:engineer|developer)\b'
states='AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC'.split()
us_pattern=r'\bUnited States\b|,\s*(?:'+'|'.join(states)+r')\s*$'
other_country_pattern=r'\b(?:United Kingdom|Canada|Australia)\b'
b=s.job_title.str.contains(backend_pattern,case=False,regex=True)
e=s.job_title.str.contains(entry_pattern,case=False,regex=True)
n=s.job_title.str.contains(nonentry_pattern,case=False,regex=True)
o=s.job_title.str.contains(occupation_pattern,case=False,regex=True)
us=s.job_location.str.contains(us_pattern,case=False,regex=True)
foreign=s.job_location.str.contains(other_country_pattern,case=False,regex=True)
geo_conflict=us & foreign
geo_us=us & ~foreign
usable_text=s.job_summary.str.strip().ne('')
strict=o&b&e&~n&geo_us&source_ids.notna()
rows_retained=~(source_ids.notna()&source_ids.duplicated())
strict_retained=strict&rows_retained


def distributions(values):
    return {str(k):int(v) for k,v in values.value_counts(dropna=False).items()}

def record(index):
    row=s.loc[index]
    return {'csv_data_row_number':int(index)+1,'posting_id':source_ids.loc[index],**{c:row[c] for c in ['job_title','company','job_location','job_link','first_seen','search_country','job level','job_type']},'summary_characters':len(row.job_summary),'summary_sha256':hashlib.sha256(row.job_summary.encode('utf-8')).hexdigest()}

def provenance(path):
    return {'path':display_path(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def display_path(path):
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)

normalize=lambda v: re.sub(r'\s+',' ',unicodedata.normalize('NFKC',v)).strip().casefold()
fallback=s[['company','job_title','job_location','job_summary']].apply(lambda c:c.map(normalize))
dupe_source_mask=source_ids.notna()&source_ids.duplicated(keep=False)
dates=pd.to_datetime(s.first_seen,format='%Y-%m-%d',errors='coerce')
nonblank_lengths=s.loc[usable_text,'job_summary'].str.len()
report={
 'report_type':'source_inspection',
 'schema_version':'1.0.0',
 'is_mock':False,
 'generated_at':generated_at,
 'status':'downloaded_and_inspected_scope_not_validated',
 'source':{
    'source_id':'kaggle:asaniczka/software-engineer-job-postings-linkedin',
    'title':metadata['title'],
    'creator':metadata['creatorName'],
    'source_url':'https://www.kaggle.com/datasets/asaniczka/software-engineer-job-postings-linkedin',
    'metadata_url':'https://www.kaggle.com/api/v1/datasets/view/asaniczka/software-engineer-job-postings-linkedin',
    'download_url':f'https://www.kaggle.com/api/v1/datasets/download/asaniczka/software-engineer-job-postings-linkedin?datasetVersionNumber={version}',
    'version':metadata['currentVersionNumber'],
    'version_published_at':metadata['lastUpdated'],
    'downloaded_at':downloaded_at,
    'download_provenance_manifest':display_path(provenance_path) if provenance_path.exists() else None,
    'download_provenance_note':download_provenance_note,
    'collection_dates':None,
    'license_name':metadata['licenseName'],
    'license_details_note':'License name is supplied by the official Kaggle API metadata; license text was not downloaded. Retain creator attribution and source URL.',
    'provenance_files':[provenance(metadata_path),provenance(zip_path),provenance(csv_path)]
 },
 'file_inspection':{
    'path':display_path(csv_path),
    'encoding':'UTF-8',
    'row_count':int(len(df)),
    'column_count':int(len(df.columns)),
    'columns':[{'name':c,'pandas_inferred_dtype':str(df[c].dtype),'null_count':int(df[c].isna().sum()),'blank_after_strip_count':int(s[c].str.strip().eq('').sum())} for c in df.columns],
    'dates':{'first_seen':{'unique_values':distributions(s.first_seen),'parse_format':'%Y-%m-%d','parse_failure_count':int(dates.isna().sum()),'min':str(dates.min().date()) if dates.notna().any() else None,'max':str(dates.max().date()) if dates.notna().any() else None,'meaning':'Field label says first_seen; it is not independently verified as publication date or scrape/collection date. Keep collection_dates null.'}},
    'distributions':{c:distributions(s[c]) for c in ['search_country','job level','job_type']},
    'text_availability':{'nonblank_job_summary_count':int(usable_text.sum()),'missing_or_blank_job_summary_count':int((~usable_text).sum()),'nonblank_summary_characters_min':int(nonblank_lengths.min()) if len(nonblank_lengths) else None,'nonblank_summary_characters_median':float(nonblank_lengths.median()) if len(nonblank_lengths) else None,'nonblank_summary_characters_max':int(nonblank_lengths.max()) if len(nonblank_lengths) else None,'scope':'Nonblank text is an availability check, not a completed requirement-usability assessment.'},
    'source_identifier_check':{'identifier':'numeric LinkedIn job ID at end of /jobs/view/ URL path','parseable_id_rows':int(source_ids.notna().sum()),'unparseable_id_rows':int(source_ids.isna().sum()),'unique_parseable_ids':int(source_ids.nunique()),'unparseable_rows':[record(i) for i in df.index[source_ids.isna()]]},
    'duplicate_diagnostics':{'exact_duplicate_row_count':int(df.duplicated().sum()),'duplicate_exact_job_link_excess_rows':int(s.job_link.duplicated().sum()),'duplicate_parseable_source_id_excess_rows':int((source_ids.notna()&source_ids.duplicated()).sum()),'normalized_company_title_location_summary_excess_rows':int(fallback.duplicated().sum()),'fallback_normalization':'Unicode NFKC, whitespace collapse, strip, casefold; all four fields must match. This is an inspection diagnostic, not the approved production deduplication rule.','source_id_duplicate_rows':[record(i) for i in df.index[dupe_source_mask]],'records_removed':0,'note':'Raw data is unchanged. No cleaning pipeline was run. Screening evaluates both raw rows and a temporary first-row-per-valid-ID view.'},
    'representative_records':[record(i) for i in sorted({0,len(df)//2,len(df)-1}) if 0<=i<len(df)],
 },
 'scope_screening':{
    'requested_scope':{'occupation':'software_developer','specialization':'backend','seniority':'entry_level','geography':'US'},
    'status':'insufficient_evidence_to_confirm_usable_scope',
    'rules_version':'inspection-title-screen-v1',
    'rules':{
       'occupation':{'input':'job_title','positive_pattern':occupation_pattern,'note':'Provisional title cue; no O*NET mapping has been performed.'},
       'specialization':{'input':'job_title','positive_pattern':backend_pattern,'unknown':'Titles without this explicit cue are unknown, not confirmed non-backend. Descriptions have not been classified.'},
       'seniority':{'input':'job_title','entry_pattern':entry_pattern,'nonentry_pattern':nonentry_pattern,'conflict':'Both entry and nonentry title cues => conflict; neither => unknown. The source job level is retained but not used as an entry-level filter. Associate does not establish entry level.'},
       'geography':{'input':'job_location','us_positive_pattern':us_pattern,'explicit_other_country_pattern':other_country_pattern,'conflict':'Both => conflict; neither => unknown. search_country is search provenance, not proof of job location or remote eligibility. No metro-area lookup or remote text inference was performed.'},
       'text':'Nonblank job_summary only for screening availability; production requirement-usability decisions pending.',
       'selection':'All positive title/location cues, no title or location conflict, parseable source ID. No filters broadened.'
    },
    'independent_counts':{
       'occupation_title_cue':int(o.sum()),
       'backend_title_cue':int(b.sum()),
       'entry_title_cue':int(e.sum()),
       'nonentry_title_cue':int(n.sum()),
       'seniority_title_conflict':int((e&n).sum()),
       'seniority_title_unknown':int((~e&~n).sum()),
       'source_mid_senior_with_entry_title_cue':int((s['job level'].eq('Mid senior')&e).sum()),
       'source_associate_with_nonentry_title_cue':int((s['job level'].eq('Associate')&n).sum()),
       'us_location_cue_without_location_conflict':int(geo_us.sum()),
       'explicit_nonus_location_cue_without_location_conflict':int((foreign&~us).sum()),
       'geography_location_conflict':int(geo_conflict.sum()),
       'geography_unknown':int((~us&~foreign).sum()),
       'backend_plus_entry_title_cues':int((b&e).sum()),
       'all_positive_scope_cues_raw_rows':int(strict.sum()),
       'all_positive_scope_cues_unique_source_ids':int(strict_retained.sum()),
       'all_positive_scope_cues_with_nonblank_summary':int((strict_retained&usable_text).sum())
    },
    'candidate_records':[record(i) for i in df.index[strict_retained]],
    'candidate_caveat':'If selected, posting 3784448460 requires TS/SCI clearance with polygraph. Its bachelor-degree OR four-year experience alternative must not be misread as four years required for all applicants. Other candidate requirements require their own review.',
    'adequacy_decision':'No final eligible_postings_count or analyzed_postings_count is published. Full description-based classification and a declared minimum sample size are still needed. This conservative screen does not establish that only one qualifying posting exists in the entire dataset.'
 },
 'data_quality':{
    'source_files_downloaded':True,
    'raw_inputs_preserved':True,
    'exclusions_performed':0,
    'missing_description_count':int((~usable_text).sum()),
    'extraction_errors':None,
    'manual_skill_audit_status':'not_performed_no_skill_extractor_implemented',
    'limitations':[
       f'This is version {version} of a scraped LinkedIn sample, published {metadata["lastUpdated"]}. It is not live market demand or a representative census.',
       'The first_seen distribution and version publication timestamp are recorded separately. Neither is asserted as an independently verified collection window.',
       'job_skills contains source-provided skill strings; their extraction method, correctness, and context have not been verified. They are not substitutes for direct job_summary evidence.',
       'Only Associate and Mid senior source labels exist, and title/description conflicts show that Associate cannot automatically mean entry level.',
       'search_country is search provenance; actual geography and remote eligibility need job_location and description checks.',
       f'{int(source_ids.isna().sum())} records have no parseable numeric posting ID. Invalid IDs and missing summaries are reported independently.',
       f'{int((source_ids.notna()&source_ids.duplicated()).sum())} excess rows share a numeric LinkedIn job ID. Compare these with exact-URL duplicates before defining the final deduplication policy.',
       'Conservative title screening deliberately leaves generic titles, metro locations, and description-only backend/entry cues unresolved.',
       'No real skill frequencies, cleaned-posting export, final role classifications, or source-specific ingestion pipeline have been generated.'
    ],
    'next_steps':[
       'Inspect a reproducible stratified sample of ambiguous titles, location-only unknowns, source-level conflicts, and summary requirements before defining classification rules.',
       'Agree what entry level includes: new graduate/junior labels, explicit zero-to-two-year requirements, internships, and degree-versus-experience alternatives.',
       'Implement raw-to-clean text transformation and source-ID/fallback deduplication with removal ledgers.',
       'Run conservative classification, preserve conflicts/unknowns, and report the actual available eligible and usable sample before any scope changes.',
       'Choose and document a minimum sample policy before publishing role frequencies; report insufficient data when needed.'
    ]
 }
}
# Sampling cues are intentionally separate from the future shared skill matcher.
# They select material for review; they are not extracted skills or human labels.
skill_cue_pattern=r'(?<![A-Za-z0-9_])(?:Python|JavaScript|Java|C\+\+|C#|\.NET|Node\.js|SQL|PostgreSQL|Postgres|AWS|Amazon Web Services|GitHub|Git|Docker|Kubernetes|scikit-learn|sklearn)(?![A-Za-z0-9_])'
ambiguous_pattern=r'(?<![A-Za-z0-9_+#])(?:C|R|Go|go|PG)(?![A-Za-z0-9_+#])'
context_pattern=r'(?i)(?:\b(?:not required|no experience required|not necessary)\b|\b(?:Python|JavaScript|Java|SQL|PostgreSQL|Go)\b.{0,40}\bor\b|\bor\b.{0,40}\b(?:Python|JavaScript|Java|SQL|PostgreSQL)\b)'
skill_cue=s.job_summary.str.contains(skill_cue_pattern,case=False,regex=True)
ambiguous_cue=s.job_summary.str.contains(ambiguous_pattern,regex=True)
context_cue=s.job_summary.str.contains(context_pattern,regex=True)
scope_conflict=(e&n)|(s['job level'].eq('Mid senior')&e)|(s['job level'].eq('Associate')&n)|geo_conflict
scope_unknown=(~e&~n)|(~us&~foreign)|~b|~o
audit_pool=rows_retained&source_ids.notna()&usable_text
strata=[
    ('scope_candidate',strict_retained),
    ('no_obvious_skill_cues',~skill_cue),
    ('ambiguous_c_r_go_pg',ambiguous_cue),
    ('negation_or_alternatives',context_cue),
    ('scope_conflicts',scope_conflict),
    ('scope_unknowns',scope_unknown),
]
seed='waypointai-manual-audit-v1'
def sample_hash(index):
    value=f'{seed}\0{metadata["ref"]}\0{version}\0{source_ids.loc[index]}'
    return hashlib.sha256(value.encode('utf-8')).hexdigest()

selected=[]
selected_ids=set()
stratum_counts=[]
for name,mask in strata:
    candidates=list(df.index[audit_pool&mask])
    candidates.sort(key=lambda index:(sample_hash(index),source_ids.loc[index],int(index)))
    chosen=[]
    for index in candidates:
        posting_id=source_ids.loc[index]
        if posting_id in selected_ids:
            continue
        chosen.append(index)
        selected_ids.add(posting_id)
        if len(chosen)==2:
            break
    stratum_counts.append({'stratum':name,'available_unique_postings':len(candidates),'selected_postings':len(chosen)})
    for index in chosen:
        raw_record=record(index)
        selected.append({
            'audit_id':f'kaggle-v{version}-{source_ids.loc[index]}',
            'selection_stratum':name,
            'matching_strata':[other_name for other_name,other_mask in strata if bool(other_mask.loc[index])],
            'selection_hash':sample_hash(index),
            'source_id':report['source']['source_id'],
            'source_version':version,
            'source_file':display_path(csv_path),
            **raw_record,
            'review_status':'pending',
            'automated_extraction':None,
            'human_review':{
                'canonical_skill_ids':None,
                'evidence_and_contexts':None,
                'occupation':None,
                'specialization':None,
                'seniority':None,
                'geography':None,
                'false_positives':None,
                'missed_skills':None,
                'notes':None,
                'reviewer':None,
                'reviewed_at':None,
            },
        })
audit={
    'schema_version':'1.0.0',
    'is_mock':False,
    'status':'pending_manual_review',
    'generated_at':generated_at,
    'vocabulary_version':None,
    'source':{'source_id':report['source']['source_id'],'source_url':report['source']['source_url'],'version':version,'file':provenance(csv_path)},
    'selection':{
        'rules_version':'inspection-audit-sampling-v1',
        'seed':seed,
        'rank':'Ascending SHA-256 of seed + NUL + dataset ref + NUL + version + NUL + numeric posting ID; ID and row number break ties.',
        'stratum_order':[name for name,_ in strata],
        'maximum_records_per_stratum':2,
        'deduplication':'First raw row per parseable numeric LinkedIn ID; once selected, an ID cannot be selected again. Earlier strata take precedence.',
        'pool':'Nonblank job_summary with parseable source ID. Search-page rows and duplicate IDs are excluded only from this audit sample, not changed in raw data.',
        'skill_cue_pattern':skill_cue_pattern,
        'ambiguous_term_pattern':ambiguous_pattern,
        'negation_or_alternatives_pattern':context_pattern,
        'scope_rules_reference':'kaggle_inspection.json#/scope_screening/rules',
        'scope_conflicts':'Conflicting entry/nonentry title cues; source Mid senior with entry title cue; source Associate with nonentry title cue; or conflicting location cues.',
        'scope_unknowns':'No seniority title cue, no location country cue, no backend title cue, or no software occupation title cue. Absence is unknown, not exclusion evidence.',
        'stratum_counts':stratum_counts,
    },
    'instructions':[
        'Review the complete raw job_summary locally by csv_data_row_number and verify its summary_sha256. Descriptions are not copied into this report. Numbers count parsed data rows starting at 1 after the header; CSV fields may span physical lines.',
        'Review all skills present in the text, including skills missed by the sampling cue list. No-obvious-skill-cues is a sampling heuristic, not a no-skills label.',
        'Record canonical IDs, exact evidence, requirement contexts, alternative groups, and uncertain cases using the agreed vocabulary version.',
        'Once an extractor exists, compare its output with human labels and complete false_positives and missed_skills. Keep these fields null until reviewed; an empty list means a completed review found none.',
        'The sample deliberately oversamples edge cases. It cannot estimate overall precision or recall without a separate representative evaluation design.',
    ],
    'metrics':{'sampled_postings_count':len(selected),'reviewed_postings_count':0,'false_positive_count':None,'missed_skill_count':None},
    'records':selected,
}
out=out_dir/'kaggle_inspection.json'
audit_out=out_dir/'manual_audit_v1.json'
out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
audit_out.write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'report':str(out),'audit':str(audit_out),'rows':len(df),'screening':report['scope_screening']['independent_counts'],'audit_sampled':len(selected),'audit_reviewed':0},indent=2))
