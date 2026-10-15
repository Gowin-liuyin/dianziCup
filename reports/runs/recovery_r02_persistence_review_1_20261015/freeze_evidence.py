from pathlib import Path
import datetime,json,subprocess,hashlib
ROOT=Path(r'D:\dianzi\reports\runs\recovery_r02_persistence_review_1_20261015')
WT=Path(r'C:\Users\yinha\.codex\worktrees\recovery-r02-review\dianzi')
def git(*args):
    return subprocess.run(['git',*args],cwd=WT,capture_output=True,text=True,check=True).stdout.strip()
result={'captured_at':datetime.datetime.now().astimezone().isoformat(),'sha':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'branch':git('branch','--show-current'),'status':git('status','--porcelain'),'baseline':'adb86df7149d2f753f4afe1e08d721160dd780fe','changed_files':git('diff','--name-status','adb86df7149d2f753f4afe1e08d721160dd780fe..HEAD').splitlines(),'lock_sha256':hashlib.sha256((WT/'backend/uv.lock').read_bytes()).hexdigest(),'pyproject_sha256':hashlib.sha256((WT/'backend/pyproject.toml').read_bytes()).hexdigest()}
assert result['sha']=='0fe642b1c9e5fe4dafa2774e9432bd96079c1b72' and result['status']==''
(ROOT/'freeze_final.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ['frozen_unit','full_unit_contract_security','auth_integration','knowledge_integration','independent_pg_negatives','independent_pg_model_negative','independent_persistence_positive','credential_failure_probe','credential_failure_probe_v2','schema_module_identity','ruff_check','ruff_format','mypy']:
    meta=json.loads((ROOT/(name+'.command.json')).read_text())
    print(name,meta['start'],meta['end'],meta['exit_code'],meta['counts'])
print(json.dumps({key:value for key,value in result.items() if key!='changed_files'},ensure_ascii=False,indent=2))
