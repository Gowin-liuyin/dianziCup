"""亲核 fix1 及初版 raw 证据、源码边界和原负例字节。"""
import gzip
import hashlib
import json
import pathlib
import subprocess
from datetime import datetime, timezone, timedelta

ROOT = pathlib.Path('D:/wt/r17-assets-review1-fix1')
AUTHOR = pathlib.Path('D:/wt/r17-assets-workbench')
RUN = ROOT / 'reports/runs/recovery_r17_assets_review1_fix1_20261016'
CODE = 'a25fd81c50f0ea14f44e7fda2c3edac5cab74d48'
MATERIAL = 'f9f041056ac717c6be2287a4ad97058538adce66'
BASE = '6db161e59e1c081d249b510ac441c93ad2fd295b'
now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
sha = lambda value: hashlib.sha256(value).hexdigest()
def git(*arguments): return subprocess.check_output(['git', *arguments], cwd=ROOT)
def write(name, value): (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

started = now(); raw_audits = {}
for label, prefix, expected in [('original', 'reports/runs/recovery_r17_assets_workbench_20261016', '8c40f723ddc65f467a1c31ee8216c159f09607e56f7fbc1ebf23b242e70192e6'), ('fix1', 'reports/runs/recovery_r17_assets_workbench_fix1_20261016', '2e72d1ba9f571a83c55f3ea6d925d2859ac343245494cfcfdc4115f9be8c99b0')]:
    manifest_raw = (ROOT / prefix / 'raw_manifest.json').read_bytes(); manifest = json.loads(manifest_raw); files = []
    for entry in manifest['files']:
        path = entry['path']; work = (ROOT / path).read_bytes(); author = (AUTHOR / path).read_bytes(); blob = git('show', f'{MATERIAL}:{path}'); index = git('show', ':0:' + path)
        original = git('show', f'{BASE}:{path}') if label == 'original' else blob
        files.append({**entry, 'review_work_sha256': sha(work), 'author_work_sha256': sha(author), 'material_blob_sha256': sha(blob), 'review_index_sha256': sha(index), 'matches_original_base': original == blob, 'verified': len(work) == entry['bytes'] and all(sha(value) == entry['sha256'] for value in [work, author, blob, index, original])})
    raw_audits[label] = {'manifest_sha256': sha(manifest_raw), 'expected_manifest_sha256': expected, 'matches': sha(manifest_raw) == expected, 'count': len(files), 'verified': sum(item['verified'] for item in files), 'files': files}
receipt = json.loads((ROOT / 'reports/runs/recovery_r17_assets_workbench_fix1_20261016/source_receipt.json').read_bytes())
sources = []
for path in receipt['code_paths']:
    work = (ROOT / path).read_bytes(); code = git('show', f'{CODE}:{path}'); index = git('show', ':0:' + path)
    sources.append({'path': path, 'work_sha256': sha(work), 'code_sha256': sha(code), 'index_equals_code': index == code, 'normalized_work_equals_code': work.replace(b'\r\n', b'\n') == code.replace(b'\r\n', b'\n')})
diff = git('diff', '--binary', BASE, CODE, '--', *receipt['code_paths']); archived = gzip.decompress((ROOT / 'reports/runs/recovery_r17_assets_workbench_fix1_20261016/business.diff.gz').read_bytes())
original_paths = ['frontend/src/features/assets/synthetic-fixtures.ts', 'frontend/src/features/assets/asset-contracts.test.ts', 'frontend/src/features/assets/asset-client.test.ts', 'frontend/tests/t42_assets_assessment_ui.test.tsx', 'frontend/e2e/r17-assets.fixture.ts', 'frontend/e2e/r17_assets_fixture.spec.ts', 'frontend/e2e/r17_graph_app_fixture.spec.ts']
forbidden_paths = ['backend', 'frontend/src/api', 'frontend/src/app', 'frontend/src/App.tsx', 'frontend/src/styles.css', 'frontend/package-lock.json', 'progress', 'contracts', 'fixtures', 'benchmarks', 'docs']
source_checks = {}
for label, revision in [('source_check', CODE), ('material_check', MATERIAL)]:
    result = subprocess.run(['git', 'show', '--check', '--format=fuller', revision], cwd=ROOT, capture_output=True); (RUN / (label + '.log')).write_bytes(result.stdout + result.stderr); source_checks[label] = {'command': ['git', 'show', '--check', '--format=fuller', revision], 'cwd': str(ROOT), 'exit_code': result.returncode, 'log': label + '.log'}
reports = {}
for label in ['oldred', 'green', 'late', 'baseline']:
    raw = (RUN / ('edge_' + label + '.log')).read_text(encoding='utf-8-sig'); parsed = json.loads(raw[raw.index('{'):]); write(label + '_report.json', parsed)
    reports[label] = {'stats': parsed['stats'], 'cases': [{'title': spec['title'], 'ok': spec['ok']} for suite in parsed['suites'] for spec in suite.get('specs', [])]}
probe_paths = [RUN / 'independent.spec.cjs', ROOT / 'reports/runs/recovery_r17_assets_workbench_fix1_20261016/independent.spec.cjs', pathlib.Path('D:/wt/r17-assets-review1/reports/runs/recovery_r17_assets_review1_20261016/independent.spec.cjs')]
probe_hashes = [sha(path.read_bytes()) for path in probe_paths]
checks = {'source_check': source_checks, 'raw_audits': raw_audits, 'sources': sources, 'diff_equal_archive': diff == archived, 'diff_sha256': sha(diff), 'diff_expected_sha256': receipt['diff_uncompressed_sha256'], 'original_tests_diff': git('diff', '--name-only', BASE, MATERIAL, '--', *original_paths).decode(), 'forbidden_diff': git('diff', '--name-only', BASE, MATERIAL, '--', *forbidden_paths).decode(), 'all_production_and_test_paths': git('diff', '--name-only', BASE, CODE, '--', 'frontend').decode().splitlines(), 'probe_paths': [str(path) for path in probe_paths], 'probe_hashes': probe_hashes, 'browser': reports, 'started_at': started, 'finished_at': now(), 'command': ['python', 'reports/runs/recovery_r17_assets_review1_fix1_20261016/audit_author.py'], 'cwd': str(ROOT)}
write('author_byte_audit.json', checks)
assert all(item['matches'] and item['verified'] == item['count'] for item in raw_audits.values())
assert all(item['index_equals_code'] and item['normalized_work_equals_code'] for item in sources)
assert not checks['original_tests_diff'] and not checks['forbidden_diff'] and diff == archived and sha(diff) == receipt['diff_uncompressed_sha256']
assert all(value == '349b585720d400021385ada25c714ab262b52962e677e2547e83de13ca23205b' for value in probe_hashes)
print(json.dumps({'original_raw_verified': raw_audits['original']['verified'], 'fix1_raw_verified': raw_audits['fix1']['verified'], 'probe_sha256': probe_hashes[0], 'diff_equal': diff == archived, 'scope_source_files': len(sources), 'browser': {label: report['stats'] for label, report in reports.items()}, 'exit_code': 0}, ensure_ascii=False))
