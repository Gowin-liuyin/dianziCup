"""Check frozen material blobs, original reviewer bytes, and exact case denominators."""

import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path('D:/wt/r10-graph-recheck1')
AUTHOR = Path('D:/wt/r10-pg-graph')
RUN = Path(__file__).resolve().parent
OLD = Path('D:/dianzi/reports/runs/recovery_r10_pg_evidence_graph_review1_20261016')
FINAL = '29e1ebddca5cbadffc8c6533bdeeb08b8d63e469'
CODE = '3516b9109b9b7f2c5691d78ad0439aea4a659f4f'
PREFIX = 'reports/runs/recovery_r10_graph_validity_20261016/'


def blob(ref, path):
    return subprocess.check_output(['git', 'show', ref + ':' + path], cwd=ROOT)


manifest_bytes = blob(FINAL, PREFIX + 'artifact_manifest.json')
raw_manifest = (AUTHOR / PREFIX / 'artifact_manifest.json').read_bytes()
manifest = json.loads(manifest_bytes)
assert manifest['code_commit'] == CODE
(RUN / 'author_manifest_frozen.json').write_bytes(manifest_bytes)
receipt = {'material_sha': FINAL, 'code_sha': CODE, 'manifest_frozen_bytes': len(manifest_bytes), 'manifest_frozen_sha256': hashlib.sha256(manifest_bytes).hexdigest(), 'manifest_raw_bytes': len(raw_manifest), 'manifest_raw_sha256': hashlib.sha256(raw_manifest).hexdigest(), 'files': []}
for entry in manifest['files']:
    path = entry['path']
    assert path.startswith(PREFIX) or path in (
        'reports/tasks/R10-pg-evidence-graph.md', 'docs/decisions/CR-R10_graph_validity.md',
        'reports/runs/recovery_r10_pg_evidence_graph_20261016/cbm_validity_auth_trace.json',
        'reports/runs/recovery_r10_pg_evidence_graph_20261016/cbm_validity_field_trace.json',
    )
    raw = (AUTHOR / path).read_bytes()
    frozen = blob(FINAL, path)
    oid = subprocess.check_output(['git', 'rev-parse', FINAL + ':' + path], cwd=ROOT, text=True).strip()
    actual = {'path': path, 'raw_bytes': len(raw), 'raw_sha256': hashlib.sha256(raw).hexdigest(), 'git_blob_oid': oid, 'git_blob_bytes': len(frozen), 'git_blob_sha256': hashlib.sha256(frozen).hexdigest()}
    actual['matches'] = all(actual[key] == entry[key] for key in actual if key != 'path')
    assert actual['matches']
    if path.endswith('.xml'):
        root = ET.fromstring(frozen)
        actual['junit'] = [{key: suite.attrib.get(key) for key in ('tests', 'failures', 'errors', 'skipped')} for suite in root.iter('testsuite')]
    receipt['files'].append(actual)
code_manifest = json.loads(blob(FINAL, PREFIX + 'frozen_code_manifest.json'))
receipt['code_files'] = []
for entry in code_manifest['files']:
    path = entry['path']
    frozen = blob(CODE, path)
    raw = (AUTHOR / path).read_bytes()
    actual = {'path': path, 'raw_bytes': len(raw), 'raw_sha256': hashlib.sha256(raw).hexdigest(), 'git_blob_bytes': len(frozen), 'git_blob_sha256': hashlib.sha256(frozen).hexdigest()}
    actual['matches'] = all(actual[key] == entry[key] for key in actual if key != 'path')
    actual['material_equals_code'] = blob(FINAL, path) == frozen
    actual['review_worktree_equals_code'] = (ROOT / path).read_bytes().replace(b'\r\n', b'\n') == frozen
    assert actual['matches'] and actual['material_equals_code'] and actual['review_worktree_equals_code']
    receipt['code_files'].append(actual)
old_manifest = json.loads((OLD / 'reviewer_artifact_manifest.json').read_bytes())
receipt['old_reviewer_archive'] = []
for entry in old_manifest['files']:
    raw = Path(entry['path']).read_bytes()
    assert len(raw) == entry['raw_bytes'] and hashlib.sha256(raw).hexdigest() == entry['raw_sha256']
    receipt['old_reviewer_archive'].append({'path': entry['path'], 'matches': True})
for name in ('test_independent_graph_pg.py', 'test_graph_load_pg.py'):
    assert (OLD / name).read_bytes() == (RUN / name).read_bytes()
receipt['probe_hashes'] = {name: hashlib.sha256((RUN / name).read_bytes()).hexdigest() for name in ('test_independent_graph_pg.py', 'test_graph_load_pg.py', 'test_review2_pg.py')}
receipt['code_tree'] = subprocess.check_output(['git', 'rev-parse', CODE + '^{tree}'], cwd=ROOT, text=True).strip()
receipt['material_tree'] = subprocess.check_output(['git', 'rev-parse', FINAL + '^{tree}'], cwd=ROOT, text=True).strip()
commands = {name: json.loads(blob(FINAL, PREFIX + name)) for name in (
    'frozen_author_and_validity.json', 'frozen_regression.json', 'static_commands.json',
)}
(RUN / 'author_frozen_receipts.json').write_text(json.dumps(commands, indent=2, ensure_ascii=False), encoding='utf-8')
(RUN / 'archive_verification.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'author_entries': len(receipt['files']), 'code_entries': len(receipt['code_files']), 'old_reviewer_entries': len(receipt['old_reviewer_archive']), 'all_match': True, 'manifest_frozen_sha256': receipt['manifest_frozen_sha256'], 'manifest_raw_sha256': receipt['manifest_raw_sha256'], 'probe_hashes': receipt['probe_hashes']}, indent=2))
