"""Verify frozen hashes, index isolated source scopes and trace the actual entry points."""
import hashlib
import json
import subprocess
from pathlib import Path
from run_checks import ROOT,RUN,run,now

AUTHOR_RUN=ROOT/'reports/runs/recovery_r19_preparation_fix1_20261015'
manifest=json.loads((AUTHOR_RUN/'delivery_manifest.json').read_text(encoding='utf-8'))
CODE='22d809f7803d539a2b551eb878ceae5333182d83'
TIP='10c16a5cda132269be7d906bb902d222a41c690b'
def sha(content):
    return hashlib.sha256(content).hexdigest()
def blob(commit,path):
    return subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)
records=[]
for path,expected in manifest['canonical_code_file_sha256'].items():
    canonical=blob(CODE,path)
    observed=(ROOT/path).read_bytes()
    records.append({'path':path,'kind':'code','canonical_sha256':sha(canonical),
        'expected_match':sha(canonical)==expected,'tip_same':canonical==blob(TIP,path),
        'review_checkout_sha256':sha(observed),'normalized_checkout_same':observed.replace(b'\r\n',b'\n')==canonical})
for path,expected in manifest['report_and_run_hashes'].items():
    canonical=blob(TIP,path)
    observed=(ROOT/path).read_bytes()
    records.append({'path':path,'kind':'evidence','canonical_sha256':sha(canonical),
        'expected_match':sha(canonical)==expected['canonical_git_blob_sha256'],
        'review_checkout_sha256':sha(observed),'normalized_checkout_same':observed.replace(b'\r\n',b'\n')==canonical,
        'author_observed_explained_by_lf_crlf':expected['observed_file_sha256'] in [sha(canonical),sha(canonical.replace(b'\n',b'\r\n'))]})
original_hashes=[]
for path,expected in manifest['reviewer_public_synthetic_input_hashes'].items():
    actual=sha(Path(path).read_bytes())
    original_hashes.append({'path':path,'sha256':actual,'expected_match':actual==expected})
result={'recorded_at':now(),'code_sha':CODE,'tip_sha':TIP,'records':records,
    'original_public_fixture_binding':original_hashes,
    'all_bound':all(r['expected_match'] for r in records+original_hashes),
    'original_author_dynamic_directory_read':False}
(RUN/'frozen_binding.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
prefix=['wsl','-e','env','CBM_CACHE_DIR=/tmp/dianzi-cbm-r19-preparation-review-fix1-20261015',
    'CBM_ALLOWED_ROOT=/mnt/d/wt/r19-preparation-review-fix1','CBM_WORKERS=2',
    '/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp','cli','--json']
commands=[
    ('cbm_scripts',prefix+['index_repository','--repo-path','/mnt/d/wt/r19-preparation-review-fix1/scripts','--name','r19-preparation-review-fix1-scripts','--mode','fast','--persistence','false']),
    ('cbm_src',prefix+['index_repository','--repo-path','/mnt/d/wt/r19-preparation-review-fix1/backend/src','--name','r19-preparation-review-fix1-src','--mode','fast','--persistence','false']),
]
for function in ('validate_candidates','inspect_annotations','protected_roots','require_external','scan_leaks'):
    commands.append(('cbm_trace_'+function,prefix+['trace_path','--project','r19-preparation-review-fix1-scripts','--function-name',function,'--direction','inbound','--depth','3','--include-evidence','true','--format','json']))
results=[run(*command) for command in commands]
(RUN/'cbm_commands.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'bound_records':len(records),'original_public_bindings':len(original_hashes),
    'all_bound':result['all_bound'],'cbm_exit_codes':[r['exit_code'] for r in results]},ensure_ascii=False))
raise SystemExit(0 if result['all_bound'] and all(r['exit_code']==0 for r in results) else 1)
