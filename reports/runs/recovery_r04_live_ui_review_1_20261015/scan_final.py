"""Scan review evidence and static frontend inputs without persisting credential values."""
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

run = Path(__file__).resolve().parent
report = Path('D:/dianzi/reports/reviews/recovery/G-B-R04-live-ui-review-1.md')
frontend = Path.home() / '.codex/worktrees/r04-real-pipeline/dianzi/frontend'
new_frontend = Path.home() / '.codex/worktrees/r04-ui-time-review/dianzi/frontend'
manifest_path = run / 'credential_scan_final.json'
identity_values = [os.environ[name] for name in ('DIANZI_E2E_USERNAME','DIANZI_E2E_PASSWORD')]
fragments = {value.encode() for value in identity_values}
for value in identity_values:
    if len(value) >= 8:
        fragments.update(value[index:index+8].encode() for index in range(len(value)-7))
paths = {report}
paths.update(path for path in run.rglob('*') if path.is_file() and path != manifest_path)
paths.update(path for path in (frontend / 'src').rglob('*') if path.is_file())
paths.update(path for path in (frontend / 'dist').rglob('*') if path.is_file())
paths.update(path for path in (new_frontend / 'src').rglob('*') if path.is_file())
files = []
hits = []
for file in sorted(paths):
    content = file.read_bytes()
    hit_count = sum(fragment in content for fragment in fragments)
    files.append({'path':str(file),'size_bytes':len(content),'sha256':hashlib.sha256(content).hexdigest(),'actual_credential_fragment_hits':hit_count})
    if hit_count:
        hits.append(str(file))
session_artifacts = [str(path) for path in run.rglob('*') if path.is_file() and (path.suffix.lower() in {'.zip','.webm'} or 'storagestate' in path.name.lower())]
manifest = {'scanned_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'scope':'all own evidence files and report, PNG binary, fixed frontend src and any existing dist','checks':'both actual identity values and every contiguous 8-character fragment; no scan values persisted','file_count':len(files),'credential_hit_count':len(hits),'credential_hit_paths':hits,'forbidden_session_artifact_paths':session_artifacts,'files':files}
manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'files_scanned':len(files),'credential_hits':len(hits),'forbidden_session_artifacts':len(session_artifacts)}))
raise SystemExit(0 if not hits and not session_artifacts else 2)
