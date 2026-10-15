import json
from pathlib import Path
import subprocess

RUN = Path(__file__).parent
ROOT = Path('D:/wt/gb-stage-review')
audit = json.loads((RUN / 'classification_audit.json').read_text(encoding='utf-8'))
paths = {}
for item in audit['records']:
    if item['hash_ok'] and item['blob_hash_ok']:
        continue
    raw = (ROOT / item['path']).read_bytes()
    blob = subprocess.check_output(['git','show','1ff54965a0dd2e4f4a13245cee8dd59d2b3fdcfc:' + item['path']],cwd=ROOT)
    assert raw.replace(b'\r\n',b'\n') == blob.replace(b'\r\n',b'\n')
    path = paths.setdefault(item['path'],{'path':item['path'],'manifest_sha256':item['manifest_sha256'],'initial_checkout_sha256':item['wt_sha256'],'initial_blob_sha256':item['blob_sha256'],'raw_rejected_records':0,'blob_mismatch_records':0,'reason':'Only CRLF/LF conversion; normalized bytes identical'})
    path['raw_rejected_records'] += not item['hash_ok']
    path['blob_mismatch_records'] += not item['blob_hash_ok']
(RUN / 'initial_byte_failures.json').write_text(json.dumps(list(paths.values()),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'unique_paths':len(paths),'wt_hash_failed_records':sum(x['raw_rejected_records'] for x in paths.values()),'blob_hash_failed_records':sum(x['blob_mismatch_records'] for x in paths.values()),'all_normalized_byte_comparisons_equal':True}))
