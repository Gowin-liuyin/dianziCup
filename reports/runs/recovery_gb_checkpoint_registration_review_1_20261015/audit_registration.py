from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('D:/wt/gb-register-review')
RUN = Path(__file__).parent
BASE = '1927eeb00a7e0c1335f76340b0382f46102f08f2'
HEAD = sys.argv[1] if len(sys.argv) > 1 else 'ab097347bba7e0008b4337fa2c985452308feed6'
started = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')

def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)

def strict_pairs(items):
    result = {}
    for key,value in items:
        assert key not in result, key
        result[key] = value
    return result

def read_json(raw):
    return json.loads(raw,object_pairs_hook=strict_pairs)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

assert git('rev-parse','HEAD').decode().strip() == HEAD
subprocess.run(['git','merge-base','--is-ancestor',BASE,HEAD],cwd=ROOT,check=True)
protected = ['AGENTS.md','backend','frontend','contracts','scripts','infra','config','docs/plan','docs/tasks']
protected_identity = {name:git('rev-parse',BASE + ':' + name).decode().strip() == git('rev-parse','HEAD:' + name).decode().strip() for name in protected if (ROOT / name).exists()}
assert all(protected_identity.values())
old = read_json(git('show',BASE + ':progress/task_state.json'))
new = read_json((ROOT / 'progress/task_state.json').read_bytes())
allowed_slices = {'R04:T09','R04:T10','R04:T12','R04:T17','R04:T40','R04:T41','R05:T18','R05:T20','R05:T30','R05:T31','R05:T43'}
slices = []
for task_id,original in old['tasks'].items():
    current = new['tasks'][task_id]
    for field in set(original) | set(current):
        if field != 'slice_acceptance':
            assert original.get(field) == current.get(field), (task_id,field)
    for slice_id,item in original.get('slice_acceptance',{}).items():
        target = current['slice_acceptance'][slice_id]
        if slice_id not in allowed_slices:
            assert item == target, slice_id
            continue
        assert item['status'] == 'pending' and target['status'] == 'accepted'
        assert target['review_ref'] == 'reports/reviews/recovery/G-B-checkpoint-review-1.md'
        assert target['history'][-1]['prior_record'] == item
        assert target['history'][-1]['recorded_at'] == '2026-10-15T19:08:27+08:00'
        assert all((ROOT / path).exists() for path in target['evidence'])
        slices.append({'task':task_id,'slice':slice_id,'prior_status':item['status'],'status':target['status']})
assert {item['slice'] for item in slices} == allowed_slices
recovery_changes = {}
for task_id,item in old['recovery_tasks'].items():
    target = new['recovery_tasks'][task_id]
    if item == target:
        continue
    recovery_changes[task_id] = sorted(key for key in set(item) | set(target) if item.get(key) != target.get(key))
    assert task_id in {'R04','R05','R06'}, task_id
    if task_id == 'R06':
        assert item['status'] == 'pending' and target['status'] == 'in_progress'
        assert item['implementation'] == 'not_started' and target['implementation'] == 'partial'
        assert item['verification'] == target['verification']
        continue
    assert item['status'] == 'awaiting_review' and target['status'] == 'accepted'
    assert item['implementation'] == target['implementation'] == 'complete'
    assert target['verification']['manual'] == 'not_run'
    assert all(value == 'passed' for key,value in target['verification'].items() if key != 'manual')
    assert target['review_ref'] == 'reports/reviews/recovery/G-B-checkpoint-review-1.md'
    assert target['history'][:len(item['history'])] == item['history']

archive = ROOT / 'reports/runs/recovery_gb_checkpoint_review_1_20261015'
original = Path('D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015')
manifest = read_json((archive / 'artifact_manifest.json').read_bytes())
checks = []
for item in manifest['files']:
    path = archive / item['path']
    original_path = original / item['path']
    relative = path.relative_to(ROOT).as_posix()
    checks.append({'path':item['path'],'expected':item['sha256'],'candidate_checkout_ok':digest(path.read_bytes()) == item['sha256'],'candidate_blob_ok':digest(git('show','HEAD:' + relative)) == item['sha256'],'original_delivery_ok':digest(original_path.read_bytes()) == item['sha256']})
assert all(item['candidate_checkout_ok'] and item['candidate_blob_ok'] and item['original_delivery_ok'] for item in checks)
for name in ['artifact_manifest.json','delivery_receipt.json']:
    assert (archive / name).read_bytes() == (original / name).read_bytes()
    assert git('show','HEAD:' + (archive / name).relative_to(ROOT).as_posix()) == (original / name).read_bytes()
report_path = ROOT / 'reports/reviews/recovery/G-B-checkpoint-review-1.md'
assert digest(report_path.read_bytes()) == manifest['report_sha256'] == '50cbd2152686af6d436514208ddd3f5fcd7116cb86b7729cfc0050974594ea32'
report_blob_sha256 = digest(git('show','HEAD:' + report_path.relative_to(ROOT).as_posix()))
report_blob_matches_delivery = report_blob_sha256 == manifest['report_sha256']
extras = {path.relative_to(archive).as_posix() for path in archive.rglob('*') if path.is_file()} - {item['path'] for item in manifest['files']}
assert extras == {'.gitattributes','artifact_manifest.json','delivery_receipt.json'},extras
inventory = read_json((ROOT / 'reports/runs/recovery_r05_controller_20261015/gb_review_archive_inventory.json').read_bytes())
assert all(digest((ROOT / item['path']).read_bytes()) == item['sha256'] and digest(git('show','HEAD:' + item['path'])) == item['sha256'] for item in inventory['files'])

manifest_path = 'reports/security/recovery_fixture_false_positives.json'
raw = git('show','HEAD:' + manifest_path)
assert raw == git('show',BASE + ':' + manifest_path)
classification = read_json(raw)['records']
sys.path.insert(0,str(ROOT))
from scripts.security_scan import PATTERNS
classification_checks = []
source_paths = set()
for item in classification:
    path = ROOT / item['path']
    text = path.read_text(encoding='utf-8',errors='ignore')
    matches = [match for match in PATTERNS[item['pattern_id']].finditer(text) if match.start() == item['start'] and match.end() == item['end']]
    assert digest(path.read_bytes()) == item['raw_sha256'] == digest(git('show','HEAD:' + item['path']))
    assert len(matches) == 1 and item['match_value'] in matches[0].group(0)
    source_path = item['fixture_origin']['source_path']
    assert git('show','HEAD:' + source_path) == git('show',BASE + ':' + source_path)
    source_paths.add(source_path)
    classification_checks.append({'path':item['path'],'start':item['start'],'end':item['end'],'pattern_id':item['pattern_id'],'raw_blob_span_ok':True,'origin_source_blob_unchanged':True})

decisions = ['docs/decisions/CR-R04-R04_source_commit.md','docs/decisions/CR-R04-R05_question_commit.md','docs/decisions/CR-R04_schema_format_checks.md']
assert all((ROOT / path).read_text(encoding='utf-8').startswith(git('show',BASE + ':' + path).decode('utf-8').replace('\r\n','\n')) for path in decisions)
old_stage = git('show',BASE + ':reports/stages/recovery/G-B.md').decode('utf-8').replace('\r\n','\n')
new_stage = (ROOT / 'reports/stages/recovery/G-B.md').read_text(encoding='utf-8')
first_created = [line for line in old_stage.splitlines() if line.startswith('文档首次创建时间：')]
assert first_created == [line for line in new_stage.splitlines() if line.startswith('文档首次创建时间：')]
secret = read_json((ROOT / 'reports/runs/recovery_r01_controller_20261014/gb_final_registration_secret_scan.json').read_bytes())
assert secret['checked_secret_references'] == 9 and secret['checked_patterns'] == 321 and secret['matches'] == 0
ended = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
result = {'started_at':started,'ended_at':ended,'base':BASE,'head':HEAD,'tree':git('rev-parse','HEAD^{tree}').decode().strip(),'protected_tree_identity':protected_identity,'original_T_non_slice_fields_unchanged':True,'accepted_slices':slices,'recovery_changes':recovery_changes,'archive_index_entries':len(checks),'archive_hash_checks':checks,'archive_extra_files':sorted(extras),'controller_inventory_files':len(inventory['files']),'old_report_sha256':manifest['report_sha256'],'old_report_blob_sha256':report_blob_sha256,'old_report_blob_matches_delivery':report_blob_matches_delivery,'classification_records':len(classification_checks),'classification_checks':classification_checks,'source_origin_unique_paths_unchanged':len(source_paths),'first_created':first_created,'CR_original_prefixes_unchanged':True,'author_secret_scan_metadata':{key:secret[key] for key in ['started_at','ended_at','checked_secret_references','checked_patterns','matches']},'actual_secret_scan_by_reviewer':'not_run_no_secret_values_read','product_reruns_paid_calls':0}
(RUN / ('registration_audit_' + HEAD[:7] + '.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({key:value for key,value in result.items() if key not in {'archive_hash_checks','classification_checks','accepted_slices'}},ensure_ascii=False))
raise SystemExit(0 if report_blob_matches_delivery else 2)
