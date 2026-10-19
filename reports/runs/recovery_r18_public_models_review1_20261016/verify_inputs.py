"""Verify Git material bytes and preserve the independently read review inputs."""
from __future__ import annotations
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path('D:/wt/r18pm-r1')
RUN=Path(__file__).resolve().parent
BASE='1315194a8ee421b7f1131a901221f31f4cacb536'
SOURCE='be4b9114eafaf2556f4cb54fefdfdaa2e1cc8958'
MATERIAL='08fb9623f4cdda0facd1314ab8174376a6504798'
AUTHOR_RUN='reports/runs/recovery_r18_public_extension_models_20261016/'
ZONE=ZoneInfo('Asia/Shanghai')

def git_bytes(spec: str) -> bytes:
    return subprocess.run(['git','show',spec],cwd=ROOT,capture_output=True,check=True).stdout

def blob_id(spec: str) -> str:
    return subprocess.run(['git','rev-parse',spec],cwd=ROOT,capture_output=True,check=True).stdout.decode().strip()

def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()

started_at=datetime.now(ZONE)
selected=[AUTHOR_RUN+'payload_manifest_mode_fix.json',AUTHOR_RUN+'dependency_inventory_mode_fix.json',
          AUTHOR_RUN+'mode_source_freeze.json','reports/tasks/R18-public-extension-models.md']
manifest=json.loads(git_bytes(MATERIAL+':'+selected[0]))
inventory=json.loads(git_bytes(MATERIAL+':'+selected[1]))
target=RUN/'frozen_author_inputs'
target.mkdir(exist_ok=True)
for path in selected:
    (target/Path(path).name).write_bytes(git_bytes(MATERIAL+':'+path))
material_checks=[]
for item in manifest['payloads']:
    spec=MATERIAL+':'+item['path']
    payload=git_bytes(spec)
    material_checks.append({'path':item['path'],'sha256':sha(payload),'git_blob':blob_id(spec),
                            'matches_raw':sha(payload)==item['raw_sha256'],
                            'matches_git':blob_id(spec)==item['git_blob'],
                            'matches_size':len(payload)==item['size_bytes']})
assert len(material_checks)==manifest['payload_count']==129
assert all(item['matches_raw'] and item['matches_git'] and item['matches_size'] for item in material_checks)
input_checks=[]
snapshot=RUN/'frozen_source_inputs'
snapshot.mkdir(exist_ok=True)
for item in inventory['inputs']:
    path=item['path']
    payload=git_bytes(SOURCE+':'+path)
    raw=(ROOT/path).read_bytes()
    source_blob=blob_id(SOURCE+':'+path)
    base_blob=blob_id(BASE+':'+path) if item['base_git_blob'] is not None else None
    current={'path':path,'source_git_blob':source_blob,'base_git_blob':base_blob,'raw_sha256':sha(raw),
             'inventory_raw_matches':sha(raw)==item['raw_sha256'],
             'inventory_raw_sha256':item['raw_sha256'],'git_payload_sha256':sha(payload),
             'checkout_diff_is_only_line_endings':raw.replace(b'\r\n',b'\n')==payload.replace(b'\r\n',b'\n'),
             'source_blob_matches':source_blob==item['source_git_blob'],
             'role':item['role']}
    assert current['source_blob_matches']
    if item['role']=='unchanged_dependency':
        assert source_blob==base_blob
    input_checks.append(current)
    output=snapshot/path
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(raw)
assert len(input_checks)==52
assert sum(item['role']=='unchanged_dependency' for item in input_checks)==49
legacy=json.loads((ROOT/'contracts/schemas/public_api_v2.json').read_bytes())
extensions=json.loads((ROOT/'contracts/schemas/public_api_extensions_v1.json').read_bytes())
assert len(legacy['$defs'])==14 and len(extensions['$defs'])==24
assert all(extensions['$defs'][name]==definition for name,definition in legacy['$defs'].items())
old_models=git_bytes(BASE+':sdk/python/ai_intel_client/models.py')
new_models=git_bytes(SOURCE+':sdk/python/ai_intel_client/models.py')
assert new_models.startswith(old_models)
binding=Path('D:/dianzi/docs/decisions/CR-R18_public_read_identity_bindings.md').read_bytes()
(RUN/'CR-R18_public_read_identity_bindings.root_snapshot.md').write_bytes(binding)
ended_at=datetime.now(ZONE)
result={'source':SOURCE,'base':BASE,'material':MATERIAL,'source_workdir':str(ROOT),
        'started_at':started_at.isoformat(),'ended_at':ended_at.isoformat(),'exit_code':0,
        'author_manifest_sha256':sha(git_bytes(MATERIAL+':'+selected[0])),
        'author_report_sha256':sha(git_bytes(MATERIAL+':'+selected[3])),
        'material_count':len(material_checks),'material_all_match':True,'materials':material_checks,
        'input_count':len(input_checks),'unchanged_dependency_count':49,'inputs':input_checks,
        'checkout_raw_mismatch_paths':[item['path'] for item in input_checks if not item['inventory_raw_matches']],
        'old_models_exact_prefix':True,'old_schema_definitions_equal':14,
        'binding_input_kind':'root_raw_snapshot_uncommitted_at_review_dispatch',
        'binding_raw_sha256':sha(binding),'binding_path':'docs/decisions/CR-R18_public_read_identity_bindings.md'}
(RUN/'verified_inputs.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in {'inputs','materials'}}))
