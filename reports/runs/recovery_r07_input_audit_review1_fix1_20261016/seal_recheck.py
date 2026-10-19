"""Seal new recheck files while checking old evidence and exact approved test secrets."""

import hashlib
import html
import json
import subprocess
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree

from checks import ROOT, RUN, DATABASE, original_resource, now

OLD = Path('D:/wt/r07-input-audit-review1/reports/runs/recovery_r07_input_audit_review1_20261016')
OLD_ROOT = OLD.parents[2]
report = ROOT / 'reports/reviews/recovery/G-C-R07-input-audit-review-1-recheck.md'
started = now()
old_manifest_raw = (OLD / 'review_manifest.json').read_bytes()
assert hashlib.sha256(old_manifest_raw).hexdigest() == '272ce2e699e18560833c0575daea47910b9c04aeb1dae28baac991c455c439fc'
for row in json.loads(old_manifest_raw)['files']:
    assert hashlib.sha256((OLD_ROOT / row['path']).read_bytes()).hexdigest() == row['raw_sha256']
original = original_resource()
databases = [original.database, DATABASE, 'test_dianzi_r07_audit_review1_261016', 'test_dianzi_r07_input_audit_20261016', 'test_dianzi_r07_input_audit_fix1_20261016']
values = {original.set(database=name).render_as_string(hide_password=False) for name in databases}
values.add(original.password)
patterns = {variant.encode() for value in values for variant in (value, html.escape(value), quote(value, safe=''), json.dumps(value)[1:-1])}
folders = [RUN, ROOT / 'reports/runs/recovery_r07_input_audit_20261016', ROOT / 'reports/runs/recovery_r07_input_audit_fix1_20261016', OLD]
paths = {path for folder in folders for path in folder.rglob('*') if path.is_file() and '__pycache__' not in path.parts}
paths.add(report)
paths.update((ROOT / 'backend/src/ai_intel/enrichment/job_service.py', ROOT / 'backend/tests/security/test_r07_input_audit_fix1_acl_pg.py', ROOT / 'reports/tasks/R07-input-audit-fix1.md'))
matches, usernames = [], []
marker = b'test_dianzi_r01_20261014'
auth_prefix = ('postgresql+psycopg://' + original.username + ':***@').encode()
frozen_auth_paths = {ROOT / ('reports/runs/recovery_r07_input_audit_fix1_20261016/default_scope_metadata.' + suffix) for suffix in ('log', 'xml')}
frozen_auth_occurrences = []
for path in sorted(paths):
    if not path.exists() or path.name in ('recheck_manifest.json', 'exact_secret_scan.json', 'test_summary.json'):
        continue
    raw = path.read_bytes()
    if any(pattern in raw for pattern in patterns):
        matches.append(str(path))
    count = raw.count(original.username.encode())
    if count:
        public_count = raw.count(marker)
        auth_count = raw.count(auth_prefix) if path in frozen_auth_paths else 0
        assert count == public_count + auth_count, 'unclassified username occurrence; contents withheld'
        if public_count:
            usernames.append({'path': str(path), 'count': public_count, 'classification': 'exact public base test database marker collision', 'public_marker': marker.decode()})
        if auth_count:
            frozen_auth_occurrences.append({'path': str(path), 'count': auth_count, 'classification': 'frozen author actual test authentication username in password-masked Engine URL; full DSN/password absent; original bytes retained, reported separately'})
assert not matches, 'actual secret detected; contents withheld'
(RUN / 'exact_secret_scan.json').write_bytes(json.dumps({'started_at': started, 'ended_at': now(), 'files_scanned': len(paths), 'dsn_values_scanned': len(databases), 'password_values_scanned': 1, 'raw_and_junit_matches': [], 'username_public_marker_collisions': usernames, 'frozen_author_masked_auth_username_occurrences': frozen_auth_occurrences, 'unclassified_username_matches': 0, 'values_or_value_hashes_recorded': False, 'production_model_keys_holdout_caches': 'not read', 'original_reviewer147_raw_preserved': True}, indent=2).encode())
summary = []
for path in sorted(RUN.glob('*.xml')):
    suites = list(ElementTree.parse(path).getroot().iter('testsuite'))
    counts = {name: sum(int(suite.attrib.get(name, '0')) for suite in suites) for name in ('tests', 'failures', 'errors', 'skipped')}
    cases = [{'class': case.attrib.get('classname', ''), 'name': case.attrib['name'], 'outcome': 'failed' if case.find('failure') is not None else 'error' if case.find('error') is not None else 'skipped' if case.find('skipped') is not None else 'passed'} for suite in suites for case in suite.findall('testcase')]
    summary.append({'label': path.stem, 'counts': counts, 'cases': cases})
(RUN / 'test_summary.json').write_bytes(json.dumps(summary, indent=2).encode())
rows = []
for path in sorted([*RUN.rglob('*'), report]):
    if not path.is_file() or '__pycache__' in path.parts or path.name == 'recheck_manifest.json':
        continue
    raw = path.read_bytes()
    rows.append({'path': path.relative_to(ROOT).as_posix(), 'bytes': len(raw), 'raw_sha256': hashlib.sha256(raw).hexdigest(), 'lf_sha256': hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()})
receipt = {'created_at': now(), 'reviewer': '/root/r07_input_audit_first_independent_review', 'verdict': 'Ship, limited to input audit ACL fix1', 'source_sha': '0c57b559fe2f0d93f8a5359383f1db6cc7abc6f5', 'source_tree': '295ecfd6f68422a63118b9e70069fc4b0085ea9b', 'material_sha': '648c71795e1bea34511ec0d04348f35f6463a5e6', 'author_manifest_git_raw_sha256': '50c03a99d779a44f4619a25867421213a4dd024da0c0894822bfc61cb93e48ae', 'original_review_manifest_sha256': '272ce2e699e18560833c0575daea47910b9c04aeb1dae28baac991c455c439fc', 'tracked_business_ddl_state_attrs_locks_gold_holdout_old_assertions_changed': False, 'push_or_accepted': False, 'original_nvd_red_closed': False, 'files': rows}
(RUN / 'recheck_manifest.json').write_bytes(json.dumps(receipt, indent=2).encode())
print(json.dumps({'files': len(rows), 'raw_junit_secret_matches': 0, 'unclassified_username_matches': 0, 'frozen_author_masked_auth_username_occurrences': sum(row['count'] for row in frozen_auth_occurrences), 'public_marker_paths': len(usernames), 'report_sha256': hashlib.sha256(report.read_bytes()).hexdigest(), 'manifest_sha256': hashlib.sha256((RUN / 'recheck_manifest.json').read_bytes()).hexdigest()}))
