"""Independent Git batch object checks preserve source, original review and raw failure material."""

import hashlib
import json
import subprocess
from pathlib import Path

from checks import ROOT, RUN, now

MATERIAL = '648c71795e1bea34511ec0d04348f35f6463a5e6'
CODE = '0c57b559fe2f0d93f8a5359383f1db6cc7abc6f5'
BASE = '014de585413c8a82a04d00b1ff2fbd1ff62d733b'
AUTHOR = ROOT / 'reports/runs/recovery_r07_input_audit_fix1_20261016'
OLD = Path('D:/wt/r07-input-audit-review1/reports/runs/recovery_r07_input_audit_review1_20261016')
OLD_ROOT = OLD.parents[2]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git_blobs(refs):
    refs = list(dict.fromkeys(refs))
    result = subprocess.run(['git', 'cat-file', '--batch'], input=('\n'.join(refs) + '\n').encode(), cwd=ROOT, capture_output=True, check=True)
    remaining = memoryview(result.stdout)
    blobs = {}
    position = 0
    for reference in refs:
        end = result.stdout.index(b'\n', position)
        header = result.stdout[position:end].split()
        assert header[1] == b'blob', 'missing or non-blob frozen reference'
        size = int(header[2])
        start = end + 1
        blobs[reference] = bytes(remaining[start:start + size])
        assert result.stdout[start + size:start + size + 1] == b'\n'
        position = start + size + 1
    assert position == len(result.stdout)
    return blobs


started = now()
manifest_checkout_raw = (AUTHOR / 'raw_manifest.json').read_bytes()
manifest_raw = subprocess.check_output(['git', 'show', MATERIAL + ':reports/runs/recovery_r07_input_audit_fix1_20261016/raw_manifest.json'], cwd=ROOT)
assert digest(manifest_raw) == '50c03a99d779a44f4619a25867421213a4dd024da0c0894822bfc61cb93e48ae'
assert manifest_checkout_raw.replace(b'\r\n', b'\n') == manifest_raw.replace(b'\r\n', b'\n')
manifest = json.loads(manifest_raw)
predecessor = json.loads((AUTHOR / 'predecessor_protection.json').read_bytes())
original_manifest = json.loads((ROOT / 'reports/runs/recovery_r07_input_audit_20261016/raw_manifest.json').read_bytes())
own_old_manifest = json.loads((OLD / 'review_manifest.json').read_bytes())
assert digest((OLD / 'review_manifest.json').read_bytes()) == '272ce2e699e18560833c0575daea47910b9c04aeb1dae28baac991c455c439fc'
assert len(manifest['materials']) == 103
refs = [MATERIAL + ':' + item['path'] for item in manifest['materials']]
refs.extend(CODE + ':' + item['path'] for item in manifest['changed_source'])
refs.extend(reference + ':' + item['path'] for item in predecessor['rows'] for reference in (BASE, CODE))
refs.extend(BASE + ':' + item['path'] for item in predecessor['materials'])
refs.extend(MATERIAL + ':' + item['path'] for item in predecessor['materials'])
refs.extend(reference + ':' + item['path'] for item in predecessor['unchanged_owned_contract_metadata_types'] for reference in (BASE, CODE))
closing_paths = ['reports/runs/recovery_r07_input_audit_fix1_20261016/' + name for name in ('raw_manifest.json', 'index_blob_verification.json', 'material_fingerprint.json')]
refs.extend(MATERIAL + ':' + path for path in closing_paths)
blobs = git_blobs(refs)
results = {}
for section in ('materials', 'changed_source'):
    rows = []
    for item in manifest[section]:
        revision = MATERIAL if section == 'materials' else CODE
        frozen = blobs[revision + ':' + item['path']]
        raw = (ROOT / item['path']).read_bytes()
        assert digest(frozen) == item.get('code_git_blob_sha256', item['raw_sha256'])
        assert digest(raw.replace(b'\r\n', b'\n')) == item['lf_sha256']
        rows.append({'path': item['path'], 'git_raw_sha256': digest(frozen), 'checkout_raw_sha256': digest(raw), 'author_raw_sha256': item['raw_sha256'], 'raw_match': digest(raw) == item['raw_sha256'], 'lf_sha256': digest(raw.replace(b'\r\n', b'\n')), 'lf_match': True})
    results[section] = rows
rows = []
for item in predecessor['rows']:
    left, right = blobs[BASE + ':' + item['path']], blobs[CODE + ':' + item['path']]
    assert left == right
    assert digest(left) == item['original_git_blob_sha256'] == item['fix1_git_blob_sha256']
    rows.append({'path': item['path'], 'git_raw_sha256': digest(left), 'base_fix1_identical': True})
results['predecessor_protected'] = rows
rows = []
for item in predecessor['materials']:
    left, right = blobs[BASE + ':' + item['path']], blobs[MATERIAL + ':' + item['path']]
    assert left == right and digest(left) == item['original_git_blob_sha256']
    rows.append({'path': item['path'], 'git_raw_sha256': digest(left), 'original_material_preserved': True})
results['original_author_materials'] = rows
rows = []
for item in predecessor['unchanged_owned_contract_metadata_types']:
    assert blobs[BASE + ':' + item['path']] == blobs[CODE + ':' + item['path']]
    assert digest(blobs[CODE + ':' + item['path']]) == item['git_blob_sha256']
    rows.append({'path': item['path'], 'git_raw_sha256': item['git_blob_sha256'], 'base_fix1_identical': True})
results['owned_types_metadata_contracts'] = rows
rows = []
for item in own_old_manifest['files']:
    raw = (OLD_ROOT / item['path']).read_bytes()
    assert digest(raw) == item['raw_sha256']
    rows.append({'path': item['path'], 'raw_sha256': digest(raw), 'unchanged': True})
assert len(rows) == 147
results['original_reviewer_files'] = rows
package = subprocess.check_output(['git', 'diff', '--name-only', BASE, MATERIAL], cwd=ROOT, text=True).splitlines()
assert len(package) == 108
results['fix1_package_paths'] = package
results['closing_materials'] = []
for path in closing_paths:
    frozen = blobs[MATERIAL + ':' + path]
    author_raw = (Path('D:/wt/r07-input-audit-fix1') / path).read_bytes()
    checkout = (ROOT / path).read_bytes()
    assert frozen == author_raw
    assert checkout.replace(b'\r\n', b'\n') == frozen.replace(b'\r\n', b'\n')
    results['closing_materials'].append({'path': path, 'git_raw_sha256': digest(frozen), 'author_raw_sha256': digest(author_raw), 'checkout_raw_sha256': digest(checkout), 'original_author_bytes_preserved': True})
assert digest((ROOT / 'reports/runs/recovery_r07_input_audit_20261016/0023_input_audit_proposal.sql').read_bytes()) == 'ee2fde666548f57cdd56376e443d00592ee107a3efb4d6c169e9c1df6581bbd6'
results.update(started_at=started, ended_at=now(), source_sha=CODE, material_sha=MATERIAL, base_sha=BASE, original_raw_manifest_sha256=digest((ROOT / 'reports/runs/recovery_r07_input_audit_20261016/raw_manifest.json').read_bytes()), fix1_manifest_git_sha256=digest(manifest_raw), fix1_manifest_checkout_raw_sha256=digest(manifest_checkout_raw), fix1_manifest_checkout_lf_sha256=digest(manifest_checkout_raw.replace(b'\r\n', b'\n')), original_review_manifest_sha256=digest((OLD / 'review_manifest.json').read_bytes()), all_unchanged=True)
(RUN / 'freeze_proof.json').write_bytes(json.dumps(results, indent=2).encode())
print(json.dumps({'fix1_materials':len(results['materials']), 'fix1_sources':len(results['changed_source']), 'predecessor_protected':len(results['predecessor_protected']), 'original_author_materials':len(results['original_author_materials']), 'original_reviewer_files':len(results['original_reviewer_files']), 'all_matches':True}))
