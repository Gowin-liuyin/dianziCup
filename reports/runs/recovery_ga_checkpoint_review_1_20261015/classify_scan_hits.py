"""Classify exact and fragment collisions without disclosing any matched bytes."""
import hashlib
import json
from pathlib import Path

run=Path('/mnt/d/dianzi/reports/runs/recovery_ga_checkpoint_review_1_20261015')
config=json.loads(Path('/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json').read_text())
store=json.loads(Path('/tmp/dianzi-minio-r02-20261015/private/connection.json').read_text())
from sqlalchemy.engine import make_url
patterns={'database_password':make_url(config['TEST_DATABASE_URL']).password or '', 'minio_access_identity':store['access_key'], 'minio_secret_key':store['secret_key']}
results=[]
for path in run.rglob('*'):
    if path.is_file() and path.name not in {'scan_collision_classification.json','resource_closure_and_secret_scan.json'}:
        raw=path.read_bytes()
        for label,value in patterns.items():
            exact=raw.count(value.encode()) if value else 0
            fragments={value[i:i+8].encode() for i in range(len(value)-7)}
            matching=[hashlib.sha256(piece).hexdigest() for piece in fragments if piece in raw]
            if exact or matching: results.append(dict(file=str(path.relative_to(run)),field=label,exact_count=exact,matched_fragment_hashes=matching,sha256=hashlib.sha256(raw).hexdigest()))
(run/'scan_collision_classification.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results))
