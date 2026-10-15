import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

ROOT = Path('D:/wt/gb-stage-final')
RUN = Path(__file__).parent
SHA = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def counts(path):
    tree = ET.parse(path)
    cases = list(tree.iter('testcase'))
    errors = sum(case.find('error') is not None for case in cases)
    failed = sum(case.find('failure') is not None for case in cases)
    skipped = sum(case.find('skipped') is not None for case in cases)
    return {'total':len(cases),'pass':len(cases)-errors-failed-skipped,'fail':failed,'error':errors,'skip':skipped}

aliases = {'frontend_quality':'frontend_unit.xml','recheck_frontend_quality':'recheck_frontend_unit.xml','final_frontend_quality':'final_frontend_unit.xml'}
commands = []
for file in sorted(RUN.glob('*.command.json')):
    receipt = json.loads(file.read_text(encoding='utf-8'))
    label = receipt['label']
    xml = RUN / aliases.get(label,label + '.xml')
    receipt['counts'] = counts(xml) if xml.exists() else None
    log = RUN / (label + '.log')
    content = log.read_text(encoding='utf-8',errors='replace') if log.exists() else ''
    found = re.findall(r'(\d+) deselected',content)
    receipt['deselected'] = int(found[-1]) if found else 0
    if label in {'browser_fixture','browser_fixture_cache','final_browser_fixture'}:
        browser_path = RUN / {'browser_fixture':'browser.json','browser_fixture_cache':'browser_final.json','final_browser_fixture':'browser_1927.json'}[label]
        browser = json.loads(browser_path.read_text(encoding='utf-8'))
        stats = browser['stats']
        receipt['counts'] = {'total':stats['expected']+stats['unexpected']+stats['skipped']+stats['flaky'],'pass':stats['expected'],'fail':stats['unexpected'],'error':0,'skip':stats['skipped'],'flaky':stats['flaky']}
    commands.append(receipt)
commands.sort(key=lambda item:item['started_at'])
(RUN / 'command_summary.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2),encoding='utf-8')

def table(labels):
    rows = ['| label / 实际命令 | cwd | ISO+08 起止 | exit / 计数 |','|---|---|---|---|']
    for label in labels:
        item = next(item for item in commands if item['label'] == label)
        argv = ' '.join('"' + arg + '"' if ' ' in arg else arg for arg in item['argv'])
        argv = argv.replace('|','\\|')
        count = item['counts']
        result = ('total={total}, pass={pass}, fail={fail}, error={error}, skip={skip}'.format(**count) if count is not None else '非 pytest 检查')
        if item['deselected']:
            result += ', deselected=' + str(item['deselected'])
        rows.append(f"| `{label}`<br>`{argv}` | `{item['cwd']}` | {item['started_at']}<br>{item['ended_at']} | {item['exit_code']}；{result} |")
    return '\n'.join(rows)

historical = ['backend_full','source_security','source_details','vector_question','question_probes','deleted_evidence','knowledge_api','backend_static','frontend_quality','browser_fixture','browser_fixture_cache','official_pdf_recheck','live_provenance','recheck_backend_full','recheck_frontend_quality','semantic_smoke','plan_contract','source_idempotency__recheck','rfc850_debt']
final = ['final_uv_sync','final_npm_ci','final_backend_full','final_plan_contract','source_idempotency__final','source_formal__final','source_auth_lock__final','source_auth_lock__final_valid_fixture','source_details__final','knowledge_api__final','source_security__final','vector_question__final','question_probes__final','deleted_evidence__final','final_static','final_frontend_quality','final_browser_fixture','final_classification','final_origin']
(RUN / 'historical_commands.md').write_text(table(historical),encoding='utf-8')
(RUN / 'final_commands.md').write_text(table(final),encoding='utf-8')

inventory_paths = [ROOT / 'AGENTS.md',ROOT / 'contracts/requirements.json',ROOT / 'contracts/task_manifest.json',ROOT / 'progress/task_state.json',ROOT / 'reports/stages/recovery/G-B.md',ROOT / 'reports/tasks/R04.md',ROOT / 'reports/tasks/R05.md']
inventory_paths += [path for path in (ROOT / 'docs/plan').glob('*.md') if path.name.startswith(('00_','02_','03_','04_','05_','06_','07_','08_','09_','11_','12_'))]
inventory_paths += [path for path in (ROOT / 'docs/tasks').glob('*.md') if path.name.split('_')[0] in {'T09','T10','T12','T17','T18','T20','T30','T31','T40','T41','T43'}]
inventory_paths += list((ROOT / 'docs/decisions').glob('CR-R04*.md')) + [ROOT / 'docs/decisions/CR-R05.md']
inventory_paths += list((ROOT / 'reports/reviews/recovery').glob('G-B-*.md'))
inventory_paths += [Path('C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md'),Path('C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail/SKILL.md')]
inventory = [{'path':str(path),'bytes':path.stat().st_size,'sha256':digest(path.read_bytes())} for path in sorted(set(inventory_paths))]
(RUN / 'document_inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')

manifest_path = 'reports/security/recovery_fixture_false_positives.json'
manifest_hashes = {commit:digest(subprocess.check_output(['git','show',commit + ':' + manifest_path],cwd=ROOT)) for commit in ['1ff54965a0dd2e4f4a13245cee8dd59d2b3fdcfc','8c809c42296e3c4d064c8eaf46965303f2b8124d',SHA]}
assert len(set(manifest_hashes.values())) == 1
scanner_paths = ['scripts/security_scan.py']
scanner_changed = subprocess.check_output(['git','diff','--name-only','1ff54965a0dd2e4f4a13245cee8dd59d2b3fdcfc',SHA,'--',*scanner_paths,'.gitignore'],cwd=ROOT,text=True).splitlines()
assert not scanner_changed
coverage = json.loads((RUN / 'final_coverage.json').read_text(encoding='utf-8'))['totals']
metadata = json.loads((ROOT / 'reports/runs/recovery_gb_secret_fixture_classification_20261015/unclassified_metadata.json').read_text(encoding='utf-8'))
correction = json.loads((ROOT / 'reports/runs/recovery_gb_secret_fixture_classification_20261015/counts_correction_receipt.json').read_text(encoding='utf-8'))
before = json.loads((ROOT / 'reports/runs/recovery_r05_controller_20261015/retired_review_venvs_before.json').read_text(encoding='utf-8'))
after = json.loads((ROOT / 'reports/runs/recovery_r05_controller_20261015/retired_review_venvs_after.json').read_text(encoding='utf-8'))
assert before['entries'] == after['entries']
assert metadata['unclassified_count'] == 70 and metadata['path_count'] == 58
assert correction['proposal_counts'] == {'records':15,'unique_paths':11,'unique_spans':13}
assert correction['venv_counts'] == {'records':55,'unique_paths':47}
summary = {'recorded_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),'sha':SHA,'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip(),'backend_src_tree':subprocess.check_output(['git','rev-parse','HEAD:backend/src'],cwd=ROOT,text=True).strip(),'frontend_src_tree':subprocess.check_output(['git','rev-parse','HEAD:frontend/src'],cwd=ROOT,text=True).strip(),'manifest_sha256_by_commit':manifest_hashes,'scanner_ignore_changes':scanner_changed,'coverage':coverage,'metadata_counts':{'historical':correction['historical_counts'],'venv':correction['venv_counts'],'proposal':correction['proposal_counts']},'retired_venv_receipts_equal':True,'retired_venv_receipts':[{key:value for key,value in item.items() if key != 'files'} for item in before['entries']],'full_actual_secret_scan':'not_run_by_reviewer; author exact scan metadata cross-checked separately'}
(RUN / 'final_metadata.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'sha':SHA,'command_receipts':len(commands),'document_hashes':len(inventory),'manifest_unchanged':True,'scanner_ignore_unchanged':True,'retired_venv_receipts_equal':True,'coverage':coverage},ensure_ascii=False))
