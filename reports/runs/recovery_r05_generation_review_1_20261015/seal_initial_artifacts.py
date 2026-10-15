import datetime
import hashlib
import json
from pathlib import Path

root = Path('D:/dianzi')
run = Path(__file__).resolve().parent
report = root / 'reports/reviews/recovery/G-B-R05-generation-review-1.md'
zone = datetime.timezone(datetime.timedelta(hours=8))
files = sorted(path for path in run.iterdir() if path.is_file() and path.name != 'artifact_manifest_initial.json')
files.append(report)
records = [{'path': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in files]
manifest = {'captured_at': datetime.datetime.now(zone).isoformat(timespec='seconds'), 'head': '436455d0dedd7b125740b0d0a823a9563755e8a5', 'tree': '202f93dd517cf1e884d78a3a10a783d1ca12ed05', 'state': 'initial review sealed; two Must fix remain; no product credentials accessed', 'records': records, 'resource_state': 'test/static child processes completed; local servers/sockets closed and joined; no DB or long-running service created; clean original review worktree and external runtime retained for read-only reproduction'}
(run / 'artifact_manifest_initial.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'captured_at': manifest['captured_at'], 'files': len(records), 'report_sha256': records[-1]['sha256']}))
