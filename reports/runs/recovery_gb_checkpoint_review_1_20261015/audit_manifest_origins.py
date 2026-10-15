import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('D:/wt/gb-stage-recheck')
RUN = Path(__file__).parent
records = json.loads((ROOT / 'reports/security/recovery_fixture_false_positives.json').read_text(encoding='utf-8'))['records']
results = []
def digest(raw):
    return hashlib.sha256(raw).hexdigest()
for item in records:
    origin = item['fixture_origin']
    path = ROOT / origin['source_path']
    source = path.read_bytes()
    raw_ok = digest(source) == origin['source_sha256']
    blob_ok = None
    historical_hash_ok = None
    if origin.get('source_type','git') == 'git':
        blob_id = subprocess.check_output(['git','rev-parse',origin['source_commit'] + ':' + origin['source_path']],cwd=ROOT,text=True).strip()
        raw_blob = subprocess.check_output(['git','show',origin['source_commit'] + ':' + origin['source_path']],cwd=ROOT)
        blob_ok = blob_id == origin['source_blob']
        historical_hash_ok = origin['source_sha256'] in {digest(raw_blob),digest(raw_blob.replace(b'\r\n',b'\n')),digest(raw_blob.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))}
    else:
        reference = origin.get('source_content_git_blob')
        lf_source = source.replace(b'\r\n',b'\n')
        variants = {source,lf_source,lf_source.replace(b'\n',b'\r\n')}
        blob_ok = None if reference is None else reference in {hashlib.sha1(b'blob ' + str(len(variant)).encode() + b'\0' + variant).hexdigest() for variant in variants}
        historical_hash_ok = origin['source_sha256'] in {digest(variant) for variant in variants}
    line = source.decode('utf-8').splitlines()[origin['source_line'] - 1]
    results.append({'path':item['path'],'source_path':origin['source_path'],'source_type':origin.get('source_type','git'),'current_source_raw_hash_ok':raw_ok,'source_blob_ok':blob_ok,'historical_source_sha_raw_or_checkout_eol_ok':historical_hash_ok,'source_line':origin['source_line'],'literal_at_source_line':item['match_value'] in line,'review_ref_exists':(ROOT / item['review_ref']).is_file()})
report = {'record_count':len(results),'origin_metadata':results,'source_blob_checked':sum(x['source_blob_ok'] is not None for x in results),'source_blob_passed':sum(x['source_blob_ok'] is True for x in results),'historical_source_hash_passed':sum(x['historical_source_sha_raw_or_checkout_eol_ok'] for x in results)}
(RUN / (sys.argv[2] if len(sys.argv) > 2 else 'manifest_origins.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({key:value for key,value in report.items() if key != 'origin_metadata'}))
