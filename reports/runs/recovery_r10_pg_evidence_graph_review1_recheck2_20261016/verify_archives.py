"""Verify final author raw bodies and exact frozen blobs using the supplied material SHA."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from review_runner import ROOT, RUN

AUTHOR = Path('D:/wt/r10-graph-fix2')
FINAL = sys.argv[1]
CODE = '08b141bd437c1de70a8435a1f7f6c448a131ed0d'
PREFIX = 'reports/runs/recovery_r10_graph_fix2_20261016/'

def blob(ref, path):
    return subprocess.check_output(['git','show',ref+':'+path],cwd=ROOT)

manifest_bytes = blob(FINAL,PREFIX+'artifact_manifest.json')
raw_manifest = (AUTHOR/PREFIX/'artifact_manifest.json').read_bytes()
manifest = json.loads(manifest_bytes)
assert manifest.get('code_commit',manifest.get('code_sha')) in (CODE,'11d24131aff176cc97f138d2e4a222cd378590d4')
(RUN/'author_manifest_frozen.json').write_bytes(manifest_bytes)
receipt = {'material_sha':FINAL,'code_sha':CODE,
           'material_tree':subprocess.check_output(['git','rev-parse',FINAL+'^{tree}'],cwd=ROOT,text=True).strip(),
           'manifest_frozen_bytes':len(manifest_bytes),'manifest_frozen_sha256':hashlib.sha256(manifest_bytes).hexdigest(),
           'manifest_raw_bytes':len(raw_manifest),'manifest_raw_sha256':hashlib.sha256(raw_manifest).hexdigest(),'files':[]}
for entry in manifest['files']:
    path=entry['path']
    resolved=(AUTHOR/path).resolve()
    assert resolved.is_relative_to(AUTHOR.resolve()) and not Path(path).is_absolute()
    raw=resolved.read_bytes()
    frozen=blob(FINAL,path)
    oid=subprocess.check_output(['git','rev-parse',FINAL+':'+path],cwd=ROOT,text=True).strip()
    actual={'path':path,'raw_bytes':len(raw),'raw_sha256':hashlib.sha256(raw).hexdigest(),
            'git_blob_oid':oid,'git_blob_bytes':len(frozen),'git_blob_sha256':hashlib.sha256(frozen).hexdigest()}
    assert all(actual[key]==entry[key] for key in actual if key!='path'),path
    actual['matches']=True
    if path.endswith('.xml'):
        actual['junit']=[{key:int(suite.attrib[key]) for key in ('tests','failures','errors','skipped')} for suite in ET.fromstring(frozen).iter('testsuite')]
    receipt['files'].append(actual)
code_manifest=json.loads(blob(FINAL,PREFIX+'frozen_code_manifest.json'))
receipt['code_files']=[]
for entry in code_manifest['files']:
    path=entry['path']
    frozen=blob(CODE,path)
    raw=(AUTHOR/path).read_bytes()
    actual={'path':path,'raw_bytes':len(raw),'raw_sha256':hashlib.sha256(raw).hexdigest(),
            'git_blob_oid':subprocess.check_output(['git','rev-parse',CODE+':'+path],cwd=ROOT,text=True).strip(),
            'git_blob_bytes':len(frozen),'git_blob_sha256':hashlib.sha256(frozen).hexdigest()}
    assert all(actual[key]==entry[key] for key in actual if key!='path'),path
    actual['matches']=True
    actual['material_equals_code']=blob(FINAL,path)==frozen
    actual['review_worktree_equals_code']=(ROOT/path).read_bytes().replace(b'\r\n',b'\n')==frozen
    assert actual['material_equals_code'] and actual['review_worktree_equals_code'],path
    receipt['code_files'].append(actual)
preserved=json.loads((RUN/'original_archive_preservation.json').read_text(encoding='utf-8'))
receipt['old_archive_counts']=[item['files_verified'] for item in preserved]
receipt['author_junit_totals']=[{'path':item['path'],'junit':item['junit']} for item in receipt['files'] if 'junit' in item]
(RUN/'archive_verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'author_entries':len(receipt['files']),'code_entries':len(receipt['code_files']),
                  'old_entries':receipt['old_archive_counts'],'all_match':True,
                  'manifest_raw_sha256':receipt['manifest_raw_sha256'],'manifest_frozen_sha256':receipt['manifest_frozen_sha256']},indent=2))
