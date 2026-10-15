import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('D:/wt/gb-stage-review')
sys.path.insert(0, str(ROOT))
from scripts.security_scan import PATTERNS, SAFE_CATEGORIES, load_fixture_classifications, scan_repository

table = json.loads((ROOT / 'reports/security/recovery_fixture_false_positives.json').read_text(encoding='utf-8'))
records = []
for item in table['records']:
    path = item['path']
    raw = (ROOT / path).read_bytes()
    blob = subprocess.check_output(['git', 'show', 'HEAD:' + path], cwd=ROOT)
    content = (ROOT / path).read_text(encoding='utf-8',errors='ignore')
    matches = [match for match in PATTERNS[item['pattern_id']].finditer(content) if match.start() == item['start'] and match.end() == item['end']]
    records.append({'path': path, 'pattern_id': item['pattern_id'], 'start': item['start'], 'end': item['end'], 'manifest_sha256': item['raw_sha256'], 'wt_sha256': hashlib.sha256(raw).hexdigest(), 'blob_sha256': hashlib.sha256(blob).hexdigest(), 'hash_ok': hashlib.sha256(raw).hexdigest() == item['raw_sha256'], 'blob_hash_ok': hashlib.sha256(blob).hexdigest() == item['raw_sha256'], 'span_ok': len(matches) == 1, 'value_in_span': len(matches) == 1 and item['match_value'] in matches[0].group(0)})
findings = scan_repository(ROOT, load_fixture_classifications(ROOT, ROOT / 'reports/security/recovery_fixture_false_positives.json'))
report = {'records_count':len(records), 'hash_passed':sum(x['hash_ok'] for x in records),'blob_hash_passed':sum(x['blob_hash_ok'] for x in records), 'span_passed':sum(x['span_ok'] for x in records), 'records':records,'rejected': [vars(x) for x in findings if x.category not in SAFE_CATEGORIES]}
(Path(__file__).parent / (sys.argv[2] if len(sys.argv) > 2 else ('classification_audit_recheck.json' if len(sys.argv) > 1 else 'classification_audit.json'))).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k != 'records'},ensure_ascii=False))
