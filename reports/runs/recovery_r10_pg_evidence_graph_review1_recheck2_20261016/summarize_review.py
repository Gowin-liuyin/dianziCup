"""Record real JUnit denominators, observations and isolated database guards."""
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
from review_runner import ROOT, RUN, DBNAME

OLD = Path('D:/dianzi/reports/runs/recovery_r10_pg_evidence_graph_review1_20261016')
PREVIOUS = Path('D:/dianzi/reports/runs/recovery_r10_pg_evidence_graph_review1_recheck_20261016')
labels = ['original9', 'original9_repeat', 'pure', 'complete_pure', 'fresh_pg', 'shared122',
          'related103', 'legacy33', 'legacy35', 'legacy_pure10', 'legacy_pure_complete10',
          'independent8', 'late_fence6', 'late_fence6_actual']
summary = {'recorded_at': datetime.datetime.now().astimezone().isoformat(),
           'code_sha': '08b141bd437c1de70a8435a1f7f6c448a131ed0d',
           'code_tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True).strip(),
           'python': sys.executable, 'ai_intel_path': ai_intel.__file__, 'runs': []}

def names(path):
    return sorted(case.attrib['name'] for case in ET.parse(path).getroot().iter('testcase'))

for label in labels:
    root = ET.parse(RUN/(label+'.xml')).getroot()
    suite = next(root.iter('testsuite'))
    row = {'label': label, **{key: int(suite.attrib[key]) for key in ('tests', 'failures', 'errors', 'skipped')}}
    row['passed'] = row['tests'] - row['failures'] - row['errors'] - row['skipped']
    row['failed_cases'] = [case.attrib['name'] for case in root.iter('testcase') if case.find('failure') is not None]
    row['receipt'] = json.loads((RUN/(label+'.json')).read_text(encoding='utf-8'))
    summary['runs'].append(row)

assert names(RUN/'legacy33.xml') == sorted(names(OLD/'r10_pg_independent_extended.xml')+names(OLD/'r10_pg_load_exact.xml'))
assert names(RUN/'legacy35.xml') == names(OLD/'r10_pg_original.xml')
assert names(RUN/'original9.xml') == names(PREVIOUS/'independent_pg.xml')
assert set(names(RUN/'legacy35.xml')) <= set(names(RUN/'fresh_pg.xml'))
summary['case_denominators'] = {'original33_identical': True, 'original35_identical': True,
                              'original9_identical': True, 'migrated35_retained': True,
                              'original20_retained_count': len(names(OLD/'r10_pg_independent.xml'))}
summary['source_versions'] = []
for name in ('test_review2_pg.py', 'test_independent_graph_pg.py', 'test_graph_load_pg.py',
             'test_review3_pg.py', 'test_late_fence_pg_v1_early_window.py', 'test_late_fence_pg.py',
             'test_legacy_unit.py', 'test_serialization_lock_pg.py'):
    content = (RUN/name).read_bytes()
    summary['source_versions'].append({'path': name, 'raw_bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
for name in ('test_review2_pg.py', 'test_independent_graph_pg.py', 'test_graph_load_pg.py', 'test_serialization_lock_pg.py'):
    assert (RUN/name).read_bytes() == (PREVIOUS/name).read_bytes()

observations = [json.loads(line) for line in (RUN/'fresh_pg_observations.jsonl').read_text(encoding='utf-8').splitlines()]
summary['key_observations'] = [{key: value for key, value in row.items() if key not in ('body', 'snapshot')}
                              for row in observations if row['case'] in ('2000_support_rows', 'parent_then_epoch', 'parent_lock_timeout', 'non_candidate_lock')]
summary['late_window_observations'] = [{key: value for key, value in json.loads(line).items() if key != 'body'}
                                     for line in (RUN/'late_fence6_actual_observations.jsonl').read_text(encoding='utf-8').splitlines()]
private = json.loads(subprocess.check_output(['wsl','-d','Ubuntu-22.04','-u','root','--','cat','/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json']))
target = make_url(private['TEST_DATABASE_URL']).set(database=DBNAME)
assert target.host in ('localhost','127.0.0.1') and target.port == 25432 and target.username.startswith('test_')
engine = create_engine(target, connect_args={'connect_timeout': 5})
with engine.connect() as connection:
    actual_db, actual_user = connection.execute(text('SELECT current_database(),current_user')).one()
    assert actual_db == DBNAME and actual_user == target.username
    count = connection.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'test_r10_graph_%'"))
engine.dispose()
assert count == 0
summary['database_guard'] = {'actual_database': DBNAME, 'port': 25432, 'actual_database_and_user_match': True,
                           'remaining_uuid_schemas': count, 'upgrade_only': True}
assert subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True) == ''
summary['review_worktree_clean'] = True
(RUN/'review_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2),encoding='utf-8')
print(json.dumps({'counts': [{key: row[key] for key in ('label','tests','passed','failures','errors','skipped')} for row in summary['runs']],
                  'database_guard':summary['database_guard'], 'observations': summary['key_observations']}, ensure_ascii=False,indent=2))
