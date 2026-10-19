"""Bind formal recheck evidence and synthetic-only input hashes; omit all tool caches."""
import hashlib
import json
import subprocess
from pathlib import Path
from run_checks import ROOT,RUN,now

REPORT=ROOT/'reports/reviews/recovery/G-C-R19-preparation-review-1-recheck.md'
ALLOWED={
    'annotation_unittest.log','cbm_commands.json','cbm_scripts.log','cbm_src.log',
    'cbm_trace_inspect_annotations.log','cbm_trace_protected_roots.log','cbm_trace_require_external.log',
    'cbm_trace_scan_leaks.log','cbm_trace_validate_candidates.log','check_binding_cbm.py','commands.json',
    'diff_check.log','extra_probes.json','format.log','frozen_binding.json','git_identity.log',
    'initial_extra_cleanup_recovery.json','mypy.log','original_36_replay.json','original_36_replay_initial.json',
    'plan_pytest.log','probe_fix1_extra.py','probe_fix1_extra_initial.py','probe_wsl_symlinks.py',
    'real_candidate.log','replay_original_36.py','replay_original_36_initial.py','rg_callers.log','ruff.log',
    'run_checks.py','supplementary_commands.json','verify_plan.log','wsl_symlink.log','wsl_symlink_probes.json',
    'freeze_evidence.py',
}
def item(path):
    content=path.read_bytes()
    return {'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()}

formal={str(path.relative_to(ROOT)).replace('\\','/'):item(path)
    for path in sorted(RUN.iterdir()) if path.is_file() and path.name in ALLOWED}
formal[str(REPORT.relative_to(ROOT)).replace('\\','/')]=item(REPORT)
original=json.loads((RUN/'original_36_replay.json').read_text(encoding='utf-8'))
extra=json.loads((RUN/'extra_probes.json').read_text(encoding='utf-8'))
external={}
for record in original['records']+extra['records']:
    if 'argv' not in record: continue
    argv=record['argv']
    for flag in ('--input','--labels'):
        if flag not in argv: continue
        path=Path(argv[argv.index(flag)+1])
        if not path.is_absolute(): path=ROOT/path
        if path.is_relative_to(ROOT) or not path.is_file(): continue
        external[str(path)]=item(path)
result={'schema_version':1,'task':'R19-preparation-review-1-recheck','verdict':'Ship for tools/candidates preparation only',
    'frozen_at':now(),'code_sha':'22d809f7803d539a2b551eb878ceae5333182d83',
    'material_sha':'10c16a5cda132269be7d906bb902d222a41c690b',
    'reviewed_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    'worktree':str(ROOT),'branch':'codex/r19-preparation-review-fix1','closed_original_musts':[1,2,3],
    'new_confirmed_musts':[],'report_path':str(REPORT),'report_sha256':item(REPORT)['sha256'],
    'formal_evidence_files':formal,'external_explicit_synthetic_input_files':dict(sorted(external.items())),
    'excluded':['*.pyc','__pycache__','mypy cache','ruff cache','CBM cache','real holdout','real labels','secrets'],
    'author_unittest':{'passed':40,'failed':0,'skipped':0},'plan_pytest':{'passed':47,'failed':0,'skipped':0},
    'original_cli_replay':{'executed':36,'expected_exit_unchanged':True,'mismatches':original['mismatches']},
    'extra_cli_probes':{'executed':28,'mismatches':extra['mismatches']},
    'wsl_symlink_functions_passed':3,'windows_native_symlink_cli':'blocked_environment_winerror_1314',
    'whole_r19':'partial / awaiting_human_label','actual_humans':0,'human_gold_count':0,
    'formal_evaluation':'not_run','business_code_changed':False,'shared_progress_changed':False,'push':False,
    'reviewer_harness_initial_failures_preserved':[
        'original_36_replay_initial.json: stale public leak fixture, expectation unchanged after restoring clean tree',
        'probe_fix1_extra_initial.py: no-checkout cleanup assertion; no business result counted, safe cleanup and full rerun'],
}
path=RUN/'review_evidence_manifest.json'
path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'report_sha256':result['report_sha256'],'manifest_sha256':item(path)['sha256'],
    'formal_evidence_count':len(formal),'external_synthetic_inputs':len(external),'frozen_at':result['frozen_at']},ensure_ascii=False))
