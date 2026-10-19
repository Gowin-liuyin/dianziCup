"""Record real counts, fixed trees, unchanged original cases and private guards."""

import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import ai_intel
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
ROOT = Path('D:/wt/r10-graph-recheck1')
OLD = Path('D:/dianzi/reports/runs/recovery_r10_pg_evidence_graph_review1_20261016')
REPORT = Path('D:/dianzi/reports/reviews/recovery/G-C-R10-pg-evidence-graph-review-1-recheck.md')
CODE = '3516b9109b9b7f2c5691d78ad0439aea4a659f4f'
FINAL = '29e1ebddca5cbadffc8c6533bdeeb08b8d63e469'
labels = ['new_pure', 'new_pg', 'related103', 'legacy_author35', 'legacy_probe33', 'legacy_pure10', 'independent_pg', 'independent_pg_repeat', 'serialization_lock']
summary = {'recorded_at': datetime.datetime.now().astimezone().isoformat(), 'code_sha': CODE, 'code_tree': subprocess.check_output(['git', 'rev-parse', CODE+'^{tree}'], cwd=ROOT, text=True).strip(), 'material_sha': FINAL, 'material_tree': subprocess.check_output(['git', 'rev-parse', FINAL+'^{tree}'], cwd=ROOT, text=True).strip(), 'python': sys.executable, 'ai_intel_path': ai_intel.__file__, 'runs': []}


def junit_names(path):
    return sorted(case.attrib['name'] for case in ET.parse(path).getroot().iter('testcase'))


for label in labels:
    suite = next(ET.parse(RUN / (label+'.xml')).getroot().iter('testsuite'))
    item = {'label': label, **{key: int(suite.attrib[key]) for key in ('tests', 'errors', 'failures', 'skipped')}}
    item['passed'] = item['tests'] - item['errors'] - item['failures'] - item['skipped']
    item['failed_cases'] = [case.attrib['name'] for case in suite.iter('testcase') if case.find('failure') is not None]
    summary['runs'].append(item)
original_names = junit_names(OLD / 'r10_pg_independent_extended.xml') + junit_names(OLD / 'r10_pg_load_exact.xml')
assert sorted(original_names) == junit_names(RUN / 'legacy_probe33.xml')
assert junit_names(OLD / 'r10_pg_original.xml') == junit_names(RUN / 'legacy_author35.xml')
new_names = junit_names(RUN / 'new_pg.xml')
assert all(name in new_names for name in junit_names(RUN / 'legacy_author35.xml'))
summary['case_denominators'] = {'old_reviewer33_names_unchanged': True, 'old_author35_names_unchanged': True, 'migrated_author35_names_retained': True}
raw = subprocess.check_output(['wsl', '-d', 'Ubuntu-22.04', '-u', 'root', '--', 'cat', '/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json'])
private = json.loads(raw)
target = make_url(private['TEST_DATABASE_URL']).set(database='test_dianzi_r06_catalog_r10_review2_20261016')
assert target.host in ('localhost', '127.0.0.1') and target.port == 25432 and target.username.startswith('test_')
engine = create_engine(target, connect_args={'connect_timeout': 5})
with engine.connect() as connection:
    database, username = connection.execute(text('SELECT current_database(), current_user')).one()
    assert database == target.database and username == target.username
    count = connection.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'test_r10_graph_%'"))
engine.dispose()
summary['database_guard'] = {'database': database, 'port': target.port, 'actual_database_and_user_match': True, 'remaining_graph_uuid_schemas': count, 'upgrade_only': True}
summary['diff_checks'] = []
for label, ref, paths in [('code', CODE, ['backend', 'docs/decisions/CR-R10_graph_validity.md']), ('material', FINAL, [])]:
    args = ['git', 'diff', '--check', '16803ce6be9ad6adb6d89f46c594cfa420190c24', ref, '--', *paths]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    summary['diff_checks'].append({'label': label, 'command': args, 'exit_code': result.returncode, 'output': result.stdout+result.stderr})
needles = [private['postgres_password'].encode(), private['TEST_DATABASE_URL'].encode(), target.render_as_string(hide_password=False).encode()]
paths = [p for p in RUN.iterdir() if p.is_file()] + [REPORT]
matches = [str(path) for path in paths if any(needle and needle in path.read_bytes() for needle in needles)]
assert matches == []
summary['secret_scan'] = {'files_checked': len(paths), 'known_private_credential_matches': matches}
summary['worktree_status'] = subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True)
assert summary['worktree_status'] == ''
(RUN / 'review_summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
times = []
for label in labels + ['ruff', 'format', 'mypy']:
    receipt = json.loads((RUN/(label+'.json')).read_text(encoding='utf-8'))
    times.append('| `'+label+'` | '+receipt['started_at']+' | '+receipt['finished_at']+' | '+str(receipt['exit_code'])+' |')
report = REPORT.read_text(encoding='utf-8')
marker = '\n上述每组均 0 error/skip'
assert marker in report
table = '\n\n实际 +08:00 窗口（完整 argv/cwd 在同名收据）：\n\n| label | 开始 | 结束 | exit |\n|---|---|---|---|\n'+'\n'.join(times)+'\n\n'
table_start = report.find('\n\n实际 +08:00 窗口（完整 argv/cwd 在同名收据）：')
if table_start >= 0:
    report = report[:table_start] + table + report[report.index(marker, table_start):]
else:
    report = report.replace(marker, table+marker)
REPORT.write_text(report, encoding='utf-8')
print(json.dumps({'runs': summary['runs'], 'denominators': summary['case_denominators'], 'database_guard': summary['database_guard'], 'diff_checks': summary['diff_checks'], 'secret_scan': summary['secret_scan'], 'code_tree': summary['code_tree'], 'material_tree': summary['material_tree']}, indent=2, ensure_ascii=False))
