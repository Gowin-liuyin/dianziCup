"""Copy only frozen reviewer harness/probes, with distinct owned resource and output paths."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
OLD = Path('D:/wt/r07-input-audit-review1/reports/runs/recovery_r07_input_audit_review1_20261016')
ROOT = RUN.parents[2]
copies = ('checks.py', 'review_fixtures.py', 'cbm_checks.py', 'review_baseline.py', 'frozen_copies.json', 'baseline/job_contracts.py', 'baseline/job_models.py', 'baseline/job_types.py', 'baseline/job_service.py', 'probes/conftest.py', 'probes/test_independent_input_audit.py', 'probes/test_independent_legacy_completed.py', 'probes/test_independent_unicode.py', 'probes/test_independent_idempotency_scope.py')
rows = []
for name in copies:
    raw = (OLD / name).read_bytes()
    copied = raw
    if name == 'checks.py':
        copied = copied.replace(b"RUN_ID = 'r07_audit_review1_261016'", b"RUN_ID = 'r07_audit_review1_fix1_261016'").replace(b"OWNER = 'independent-review1:r07-input-audit:014de585413c8a82a04d00b1ff2fbd1ff62d733b'", b"OWNER = 'independent-review1-fix1:r07:648c71795e1bea34511ec0d04348f35f6463a5e6'")
        copied = copied.replace(b"author_run / 'nvd_current_selection_observation.json'", b"author_run / 'nvd_current_selection_observation.json'")
    elif name == 'review_fixtures.py':
        copied = copied.replace(b"SCHEMA_PREFIX = 'test_r07_review1_'", b"SCHEMA_PREFIX = 'test_r07_review1_fix1_'")
    elif name == 'cbm_checks.py':
        copied = copied.replace(b'CBM_CACHE_DIR=/tmp/dianzi-cbm-r07-audit-review1-20261016', b'CBM_CACHE_DIR=/tmp/dianzi-cbm-r07-audit-review1-fix1-20261016')
    target = RUN / name
    target.parent.mkdir(parents=True, exist_ok=True)
    assert not target.exists()
    target.write_bytes(copied)
    rows.append({'path': name, 'old_raw_sha256': hashlib.sha256(raw).hexdigest(), 'copied_raw_sha256': hashlib.sha256(copied).hexdigest(), 'byte_exact': raw == copied})
identity = {'started_at': '2026-10-16T09:35:59+08:00', 'bootstrap_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'), 'source_sha': '0c57b559fe2f0d93f8a5359383f1db6cc7abc6f5', 'source_tree': '295ecfd6f68422a63118b9e70069fc4b0085ea9b', 'material_sha': '648c71795e1bea34511ec0d04348f35f6463a5e6', 'original_report': 'D:/wt/r07-input-audit-review1/reports/reviews/recovery/G-C-R07-input-audit-review-1.md', 'original_report_sha256': '89fce892f7d5787d6c574b38fc7c277a59a0d0669311b9d7b6c5b74100318b6b', 'original_review_manifest_sha256': '272ce2e699e18560833c0575daea47910b9c04aeb1dae28baac991c455c439fc', 'copies': rows}
assert hashlib.sha256(Path(identity['original_report']).read_bytes()).hexdigest() == identity['original_report_sha256']
assert hashlib.sha256((OLD / 'review_manifest.json').read_bytes()).hexdigest() == identity['original_review_manifest_sha256']
(RUN / 'review_identity.json').write_bytes(json.dumps(identity, indent=2).encode())
(RUN / 'cbm_architecture_args.json').write_bytes(json.dumps({'project': 'r07-input-audit-review1-fix1', 'aspects': ['all'], 'format': 'json'}).encode())
print(json.dumps({'copied_files': len(rows), 'original_review_frozen': True}))
