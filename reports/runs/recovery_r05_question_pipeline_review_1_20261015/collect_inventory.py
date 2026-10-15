import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from xml.etree import ElementTree
wt = Path('D:/wt/r05-pipe-review')
run = Path('D:/dianzi/reports/runs/recovery_r05_question_pipeline_review_1_20261015')
records = {}
for path in sorted(run.glob('*.json')):
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        continue
    if 'command' not in value:
        continue
    xml_path = run / (path.stem + '.xml')
    if xml_path.exists():
        suites = ElementTree.parse(xml_path).getroot()
        rows = [suites] if suites.tag == 'testsuite' else list(suites)
        value['test_counts'] = {key: sum(int(row.attrib.get(key, 0)) for row in rows) for key in ['tests', 'failures', 'errors', 'skipped']}
    records[path.stem] = value
scripts = {str(path.relative_to(run)): hashlib.sha256(path.read_bytes()).hexdigest() for path in run.rglob('*.py')}
def git(*args):
    return subprocess.check_output(['git', *args], cwd=wt, text=True).strip()
value = {'recorded_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'), 'head': git('rev-parse', 'HEAD'), 'tree': git('rev-parse', 'HEAD^{tree}'), 'branch': git('branch', '--show-current'), 'status_short': git('status', '--short'), 'base': git('rev-parse', '168836796e4d8414ec72846769e3a6941afbb726'), 'base_tree': git('rev-parse', '168836796e4d8414ec72846769e3a6941afbb726^{tree}'), 'tests_sha': 'af73b3e66d6f984fa0071938ff302257cae09711', 'tests_tree': git('rev-parse', 'af73b3e66d6f984fa0071938ff302257cae09711^{tree}'), 'changed_files': git('diff', '--name-only', '168836796e4d8414ec72846769e3a6941afbb726', 'HEAD').splitlines(), 'uv_version': subprocess.check_output(['uv', '--version'], text=True).strip(), 'python_version': subprocess.check_output([str(wt / 'backend/.venv/Scripts/python.exe'), '--version'], text=True).strip(), 'records': records, 'script_sha256': scripts}
(run / 'review_evidence_inventory.json').write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key:value[key] for key in ['recorded_at', 'head', 'tree', 'base_tree', 'status_short', 'uv_version', 'python_version']}))
print(json.dumps({label: record.get('test_counts') for label, record in records.items() if 'test_counts' in record}))
