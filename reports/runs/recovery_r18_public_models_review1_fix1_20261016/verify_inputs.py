"""Verify fixed author materials and unchanged prior test oracles."""
from __future__ import annotations
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path('D:/wt/r18pm-r1f1')
RUN=Path(__file__).resolve().parent
BASE='08fb9623f4cdda0facd1314ab8174376a6504798'
SOURCE='011ea225d18b7511a19d7d6056288f799bb83f20'
MATERIAL='1474b1f9af37ed59cfe79ed83f5864514d45d3ec'
AUTHOR_RUN='reports/runs/recovery_r18_public_extension_models_fix1_20261016/'
ZONE=ZoneInfo('Asia/Shanghai')

def read(spec: str) -> bytes:
    return subprocess.run(['git','show',spec],cwd=ROOT,capture_output=True,check=True).stdout

def blob(spec: str) -> str:
    return subprocess.run(['git','rev-parse',spec],cwd=ROOT,capture_output=True,check=True).stdout.decode().strip()

def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

start=datetime.now(ZONE)
manifest_bytes=read(MATERIAL+':'+AUTHOR_RUN+'payload_manifest.json')
manifest=json.loads(manifest_bytes)
inventory=json.loads(read(MATERIAL+':'+AUTHOR_RUN+'dependency_inventory.json'))
author_snapshots=RUN/'frozen_author_inputs'
author_snapshots.mkdir()
for path in ('payload_manifest.json','dependency_inventory.json','source_freeze.json','reviewer_probe_inputs.json',
             'reviewer_probes.log','reviewer_probes_final.log','sdk_all_final.log','legacy_cleanup_recheck.log',
             'author_initial_overconstraint_test.py'):
    (author_snapshots/path).write_bytes(read(MATERIAL+':'+AUTHOR_RUN+path))
report_bytes=read(MATERIAL+':reports/tasks/R18-public-extension-models-fix1.md')
(author_snapshots/'R18-public-extension-models-fix1.md').write_bytes(report_bytes)
materials=[]
for item in manifest['payloads']:
    raw=read(MATERIAL+':'+item['path'])
    identifier=blob(MATERIAL+':'+item['path'])
    assert sha(raw)==item['raw_sha256'] and len(raw)==item['size_bytes'] and identifier==item['git_blob']
    materials.append({'path':item['path'],'raw_sha256':sha(raw),'size_bytes':len(raw),'git_blob':identifier,'matches':True})
assert len(materials)==manifest['payload_count']==178
snapshots=RUN/'frozen_source_inputs'
snapshots.mkdir()
inputs=[]
for item in inventory['inputs']:
    path=item['path']
    raw=(ROOT/path).read_bytes()
    payload=read(SOURCE+':'+path)
    source_blob=blob(SOURCE+':'+path)
    assert source_blob==item['source_git_blob']
    if not item['changed_by_fix1']:
        assert source_blob==blob(BASE+':'+path)==item['base_git_blob']
    assert raw.replace(b'\r\n',b'\n')==payload.replace(b'\r\n',b'\n')
    record={'path':path,'source_git_blob':source_blob,'base_git_blob':item['base_git_blob'],
            'changed_by_fix1':item['changed_by_fix1'],'raw_sha256':sha(raw),
            'author_raw_matches':sha(raw)==item['raw_sha256'],'checkout_content_matches_git':True}
    inputs.append(record)
    output=snapshots/path
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(raw)
assert len(inputs)==54 and sum(not item['changed_by_fix1'] for item in inputs)==52
old=json.loads((ROOT/'contracts/schemas/public_api_v2.json').read_bytes())
extended=json.loads((ROOT/'contracts/schemas/public_api_extensions_v1.json').read_bytes())
assert all(extended['$defs'][key]==value for key,value in old['$defs'].items()) and len(old['$defs'])==14
assert blob(SOURCE+':sdk/python/ai_intel_client/models.py')=='32b48ca953f867d4d7819de94c352d7173312489'
assert blob(SOURCE+':sdk/python/ai_intel_client/__init__.py')=='80a4c46b7374c10ba5d6eea10afc462360712e74'
assert read(SOURCE+':sdk/python/ai_intel_client/models.py').startswith(read('1315194a8ee421b7f1131a901221f31f4cacb536:sdk/python/ai_intel_client/models.py'))
schema_first=Path('D:/wt/r18pm-r1/contracts/schemas/public_api_extensions_v1.json').read_bytes()
assert schema_first==(ROOT/'contracts/schemas/public_api_extensions_v1.json').read_bytes()
probes=json.loads((RUN/'probe_inputs.json').read_bytes())
for item in probes:
    raw=(RUN/'inputs'/item['path']).read_bytes()
    assert sha(raw)==item['sha256']==sha(read(MATERIAL+':'+AUTHOR_RUN+'inputs/'+item['path']))
result={'workdir':str(ROOT),'source':SOURCE,'base':BASE,'material':MATERIAL,
        'started_at':start.isoformat(),'ended_at':datetime.now(ZONE).isoformat(),'exit_code':0,
        'author_manifest_sha256':sha(manifest_bytes),'author_report_sha256':sha(report_bytes),
        'material_count':178,'materials':materials,'input_count':54,'unchanged_dependency_count':52,
        'inputs':inputs,'source_inputs_blob_matches':True,'all_material_git_raw_matches':True,
        'checkout_author_raw_mismatch_paths':[item['path'] for item in inputs if not item['author_raw_matches']],
        'old_schema_defs_equal':14,'old_models_prefix_unchanged':True,'first_probe_schema_bytes_equal':True,
        'original_probes_bytes_unchanged':True}
(RUN/'verified_inputs.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({key:value for key,value in result.items() if key not in {'materials','inputs'}}))
