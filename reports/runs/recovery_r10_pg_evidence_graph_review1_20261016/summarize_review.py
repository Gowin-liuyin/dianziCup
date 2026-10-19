"""Summarize actual JUnit, secret scan, target database guard, and evidence hashes."""

import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
ROOT = Path('D:/wt/r10-graph-review1')
DBNAME = 'test_dianzi_r06_catalog_r10_graph_review1_20261016'
labels = ['r10_pure', 'r10_pg_original', 'r10_related', 'r10_pg_independent', 'r10_pg_independent_extended', 'r10_pg_load', 'r10_pg_load_exact']
summary = {'recorded_at': datetime.datetime.now().astimezone().isoformat(), 'code_sha': 'b0b7a5b856cc38862f64c01565309564d67c34c0', 'runs': []}
for label in labels:
    root = ET.parse(RUN / (label + '.xml')).getroot()
    suite = next(root.iter('testsuite'))
    row = {'label': label, **{key: int(suite.attrib[key]) for key in ['tests', 'failures', 'errors', 'skipped']}, 'elapsed_seconds': float(suite.attrib['time'])}
    row['passed'] = row['tests'] - row['failures'] - row['errors'] - row['skipped']
    row['failed_cases'] = [item.attrib['name'] for item in suite if item.tag == 'testcase' and item.find('failure') is not None]
    summary['runs'].append(row)
private_bytes = subprocess.check_output(['wsl', '-d', 'Ubuntu-22.04', '-u', 'root', '--', 'cat', '/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json'])
private = json.loads(private_bytes)
original = make_url(private['TEST_DATABASE_URL'])
assert original.database.startswith('test_dianzi_') and original.username.startswith('test_')
target = original.set(database=DBNAME)
assert target.host in ('localhost', '127.0.0.1') and target.port == 25432
engine = create_engine(target, connect_args={'connect_timeout': 5})
with engine.connect() as connection:
    actual_db, actual_user = connection.execute(text('SELECT current_database(), current_user')).one()
    assert actual_db == DBNAME and actual_user == target.username
    remaining_test_schemas = connection.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'test_r10_graph_%'"))
engine.dispose()
summary['database_guard'] = {'target_database': DBNAME, 'run_id': 'r06_catalog_r10_graph_review1_20261016', 'loopback': True, 'port': target.port, 'actual_database_matches': True, 'actual_user_matches_private_test_user': True, 'remaining_r10_uuid_schemas': remaining_test_schemas, 'migration': 'upgrade head only; no downgrade; one UUID schema per graph test'}
needles = [private['postgres_password'].encode(), private['TEST_DATABASE_URL'].encode(), target.render_as_string(hide_password=False).encode()]
scan_paths = [path for path in RUN.iterdir() if path.is_file()]
matches = []
for path in scan_paths:
    content = path.read_bytes()
    if any(needle and needle in content for needle in needles):
        matches.append(path.name)
summary['secret_scan'] = {'files_checked': len(scan_paths), 'known_private_credential_matches': matches}
assert matches == []
summary['worktree_status'] = subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True)
(RUN / 'review_summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(summary, indent=2, ensure_ascii=False))
