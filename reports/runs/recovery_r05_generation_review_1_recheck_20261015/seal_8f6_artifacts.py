import datetime
import hashlib
import json
from pathlib import Path
root = Path('D:/dianzi')
run = Path(__file__).resolve().parent
zone = datetime.timezone(datetime.timedelta(hours=8))
files = sorted(path for path in run.iterdir() if path.is_file() and path.name != 'artifact_manifest_recheck_8f6.json')
files.extend([root/'reports/reviews/recovery/G-B-R05-generation-review-1.md', root/'reports/reviews/recovery/G-B-R05-generation-review-1-recheck.md'])
records = [{'path': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in files]
manifest = {'captured_at': datetime.datetime.now(zone).isoformat(timespec='seconds'), 'head': '8f6bd9f62b4bfb91c61ba47caaa7d6414fe6ecce', 'tree': '1b9a94ac49b58ddd12debb40f173749dbd3110a7', 'state': 'Must 1 closed; original Must 2 inputs fixed; deferred-build branch remains with two confirmed failures', 'records': records}
(run/'artifact_manifest_recheck_8f6.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'captured_at':manifest['captured_at'], 'files':len(records), 'review_sha256':records[-1]['sha256']}))
