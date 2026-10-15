import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from xml.etree import ElementTree
wt = Path('D:/wt/r05-pipe-recheck')
run = Path('D:/dianzi/reports/runs/recovery_r05_question_pipeline_review_1_20261015/recheck_dc014c9')
def git(*args):
    return subprocess.check_output(['git', *args], cwd=wt, text=True).strip()
records = {}
for path in sorted(run.glob('*.json')):
    value = json.loads(path.read_text(encoding='utf-8-sig'))
    if 'command' not in value:
        continue
    xml_path = run / (path.stem + '.xml')
    if xml_path.exists():
        suites = ElementTree.parse(xml_path).getroot()
        rows = [suites] if suites.tag == 'testsuite' else list(suites)
        value['test_counts'] = {key: sum(int(row.attrib.get(key, 0)) for row in rows) for key in ['tests', 'failures', 'errors', 'skipped']}
    records[path.stem] = value
value = {'recorded_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'), 'head': git('rev-parse', 'HEAD'), 'tree': git('rev-parse', 'HEAD^{tree}'), 'branch': git('branch', '--show-current'), 'status_short': git('status', '--short'), 'parent': git('rev-parse', 'HEAD^'), 'parent_tree': git('rev-parse', 'HEAD^^{tree}'), 'tests_sha': '54bd6dbb88c5aed6255b49dc485b1e327fbb7119', 'tests_tree': git('rev-parse', '54bd6dbb88c5aed6255b49dc485b1e327fbb7119^{tree}'), 'repair_changed_files': git('diff', '--name-only', 'HEAD^', 'HEAD').splitlines(), 'records': records, 'script_sha256': {str(path.relative_to(run)): hashlib.sha256(path.read_bytes()).hexdigest() for path in run.rglob('*.py')}}
(run / 'review_evidence_inventory.json').write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key: value[key] for key in ['recorded_at', 'head', 'tree', 'parent', 'parent_tree', 'status_short', 'repair_changed_files']}))
print(json.dumps({label: record.get('test_counts') for label, record in records.items() if 'test_counts' in record}))
