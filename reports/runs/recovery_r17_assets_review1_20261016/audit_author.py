"""亲核冻结作者证据与 Git 字节；只写独立审查运行目录。"""
import gzip
import hashlib
import json
import pathlib
import subprocess
from datetime import datetime, timezone, timedelta

ROOT = pathlib.Path('D:/wt/r17-assets-review1')
AUTHOR = pathlib.Path('D:/wt/r17-assets-workbench')
RUN = ROOT / 'reports/runs/recovery_r17_assets_review1_20261016'
AUTHOR_PREFIX = 'reports/runs/recovery_r17_assets_workbench_20261016'
CODE = '1acf4911731f654e11b6173b24db21214d753c02'
MATERIAL = '6db161e59e1c081d249b510ac441c93ad2fd295b'
BASE = '9be85d7'
now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
sha = lambda value: hashlib.sha256(value).hexdigest()
def git(*arguments):
    return subprocess.check_output(['git', *arguments], cwd=ROOT)
def write(name, value):
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

manifest_raw = (ROOT / AUTHOR_PREFIX / 'raw_manifest.json').read_bytes()
manifest = json.loads(manifest_raw)
results = []
for entry in manifest['files']:
    path = entry['path']
    work = (ROOT / path).read_bytes()
    author = (AUTHOR / path).read_bytes()
    blob = git('show', f'{MATERIAL}:{path}')
    staged = git('show', f':0:{path}')
    results.append({'path': path, 'expected_bytes': entry['bytes'], 'expected_sha256': entry['sha256'],
                    'work_bytes': len(work), 'work_sha256': sha(work), 'author_work_sha256': sha(author),
                    'material_blob_sha256': sha(blob), 'review_index_sha256': sha(staged),
                    'verified': len(work) == entry['bytes'] and all(sha(item) == entry['sha256'] for item in [work, author, blob, staged])})
receipt = json.loads((ROOT / AUTHOR_PREFIX / 'source_receipt.json').read_bytes())
source_audit = []
for path in receipt['business_paths']:
    work = (ROOT / path).read_bytes(); blob = git('show', f'{CODE}:{path}'); stage = git('show', f':0:{path}')
    source_audit.append({'path': path, 'work_sha256': sha(work), 'code_blob_sha256': sha(blob), 'review_index_sha256': sha(stage),
                         'work_bytes': len(work), 'code_blob_bytes': len(blob), 'work_equals_blob': work == blob,
                         'git_lf_equals_work_normalized': work.replace(b'\r\n', b'\n') == blob.replace(b'\r\n', b'\n'), 'index_equals_code': stage == blob})
business_diff = git('diff', '--binary', BASE, CODE, '--', *receipt['business_paths'])
archived_diff = gzip.decompress((ROOT / AUTHOR_PREFIX / 'business.diff.gz').read_bytes())
checks = {}
for label, revision in [('source_check', CODE), ('material_check', MATERIAL)]:
    result = subprocess.run(['git', 'show', '--check', '--format=fuller', revision], cwd=ROOT, capture_output=True)
    (RUN / f'{label}.log').write_bytes(result.stdout + result.stderr)
    checks[label] = {'command': ['git', 'show', '--check', '--format=fuller', revision], 'cwd': str(ROOT), 'exit_code': result.returncode, 'log': f'{label}.log'}
reports = {}
for kind in ['baseline', 'independent']:
    raw = (RUN / f'edge_{"baseline" if kind == "baseline" else "independent"}.log').read_text(encoding='utf-8-sig')
    parsed = json.loads(raw[raw.index('{'):]); write(f'{kind}_report.json', parsed)
    specs = [spec for suite in parsed['suites'] for spec in suite.get('specs', [])]
    reports[kind] = {'stats': parsed['stats'], 'cases': [{'title': spec['title'], 'ok': spec['ok'],
        'results': [{'status': r['status'], 'duration_ms': r['duration'], 'error': r.get('error', {}).get('message')} for test in spec['tests'] for r in test['results']]} for spec in specs]}
write('author_byte_audit.json', {'recorded_at': now(), 'review_head': git('rev-parse', 'HEAD').decode().strip(), 'code': CODE, 'material': MATERIAL,
      'manifest_sha256': sha(manifest_raw), 'required_manifest_sha256': '8c40f723ddc65f467a1c31ee8216c159f09607e56f7bc1ebf23b242e70192e6',
      'manifest_files': len(results), 'verified_files': sum(item['verified'] for item in results), 'raw_files': results,
      'source_bytes': source_audit, 'business_diff_equal': business_diff == archived_diff,
      'business_diff_sha256': sha(business_diff), 'source_receipt_expected_diff_sha256': receipt['source_diff_uncompressed_sha256'],
      'checks': checks, 'original_graph_tests_equal_material_164': git('show', f'{MATERIAL}:frontend/e2e/r17_graph_app_fixture.spec.ts') == git('show', '164cae93ac888180b056a4c694011402ee387383:frontend/e2e/r17_graph_app_fixture.spec.ts'),
      'browser_results': reports})
print(json.dumps({'manifest_sha256': sha(manifest_raw), 'manifest_files': len(results), 'verified_files': sum(item['verified'] for item in results), 'source_files': len(source_audit), 'source_differences_normalized': sum(not item['git_lf_equals_work_normalized'] for item in source_audit), 'business_diff_equal': business_diff == archived_diff, 'browser': {kind: value['stats'] for kind, value in reports.items()}}, ensure_ascii=False))
