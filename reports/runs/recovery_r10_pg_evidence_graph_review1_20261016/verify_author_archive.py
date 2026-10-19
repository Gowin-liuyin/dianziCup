"""Verify frozen Git blobs and sealed report raw bytes without running author scripts."""

import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path('D:/wt/r10-graph-review1')
AUTHOR = Path('D:/wt/r10-pg-graph')
RUN = Path(__file__).resolve().parent
FINAL = '16803ce6be9ad6adb6d89f46c594cfa420190c24'
CODE = 'b0b7a5b856cc38862f64c01565309564d67c34c0'
BASE = 'cc1b1d302e22048f567475b7084bcd5490761ed2'
PREFIX = 'reports/runs/recovery_r10_pg_evidence_graph_20261016/'


def blob(ref, path):
    return subprocess.check_output(['git', 'show', ref + ':' + path], cwd=ROOT)


manifest_path = PREFIX + 'artifact_manifest.json'
manifest_bytes = blob(FINAL, manifest_path)
manifest = json.loads(manifest_bytes)
assert manifest['code_commit'] == CODE
(RUN / 'author_artifact_manifest.frozen.json').write_bytes(manifest_bytes)
raw_manifest = (AUTHOR / manifest_path).read_bytes()
receipt = {'material_commit': FINAL, 'code_commit': CODE, 'manifest_frozen_bytes': len(manifest_bytes), 'manifest_frozen_sha256': hashlib.sha256(manifest_bytes).hexdigest(), 'manifest_raw_bytes': len(raw_manifest), 'manifest_raw_sha256': hashlib.sha256(raw_manifest).hexdigest(), 'files': []}
for entry in manifest['files']:
    path = entry['path']
    assert path.startswith(PREFIX) or path == 'reports/tasks/R10-pg-evidence-graph.md'
    frozen = blob(FINAL, path)
    raw = (AUTHOR / path).read_bytes()
    oid = subprocess.check_output(['git', 'rev-parse', FINAL + ':' + path], cwd=ROOT, text=True).strip()
    actual = {'path': path, 'raw_bytes': len(raw), 'raw_sha256': hashlib.sha256(raw).hexdigest(), 'git_blob_oid': oid, 'git_blob_bytes': len(frozen), 'git_blob_sha256': hashlib.sha256(frozen).hexdigest()}
    actual['matches'] = all(actual[key] == entry[key] for key in actual if key != 'path')
    receipt['files'].append(actual)
    if path.endswith('_frozen.xml'):
        root = ET.fromstring(frozen)
        actual['junit'] = [{key: suite.attrib.get(key) for key in ('tests', 'failures', 'errors', 'skipped')} for suite in root.iter('testsuite')]
assert all(item['matches'] for item in receipt['files'])
source_files = subprocess.check_output(['git', 'diff', '--name-only', BASE, CODE], cwd=ROOT, text=True).splitlines()
receipt['code_files'] = []
for path in source_files:
    frozen = blob(CODE, path)
    material = blob(FINAL, path)
    working = (ROOT / path).read_bytes()
    receipt['code_files'].append({'path': path, 'bytes': len(frozen), 'sha256': hashlib.sha256(frozen).hexdigest(), 'material_equals_code': material == frozen, 'worktree_normalized_equals_code': working.replace(b'\r\n', b'\n') == frozen})
commands = json.loads(blob(FINAL, PREFIX + 'commands_frozen.json'))
(RUN / 'author_commands_frozen.copy.json').write_text(json.dumps(commands, indent=2, ensure_ascii=False), encoding='utf-8')
(RUN / 'author_archive_verification.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'manifest_frozen_sha256': receipt['manifest_frozen_sha256'], 'manifest_frozen_bytes': len(manifest_bytes), 'manifest_raw_sha256': receipt['manifest_raw_sha256'], 'manifest_raw_bytes': len(raw_manifest), 'entries_checked': len(receipt['files']), 'all_match': True, 'frozen_junit': [item for item in receipt['files'] if 'junit' in item]}, ensure_ascii=False, indent=2))
