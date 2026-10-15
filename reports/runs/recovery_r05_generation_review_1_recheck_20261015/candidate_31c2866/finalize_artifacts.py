from __future__ import annotations
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

root=Path('D:/dianzi')
run=root/'reports/runs/recovery_r05_generation_review_1_recheck_20261015'
new=run/'candidate_31c2866'
report=root/'reports/reviews/recovery/G-B-R05-generation-review-1-recheck.md'
raw=json.loads((new/'unit_original_60.coverage.json').read_text(encoding='utf-8'))['totals']['percent_covered']
text=report.read_text(encoding='utf-8-sig').replace('__COMPLETED_AT__','2026-10-15T15:00:05+08:00').replace('__RAW_COVERAGE__',str(raw))
report.write_text(text,encoding='utf-8')
assert '__COMPLETED_AT__' not in text and '__RAW_COVERAGE__' not in text
zone=datetime.timezone(datetime.timedelta(hours=8))
paths=sorted(path for path in run.rglob('*') if path.is_file() and '__pycache__' not in path.parts and path.name!='artifact_manifest_final_31.json')
paths.extend([root/'reports/reviews/recovery/G-B-R05-generation-review-1.md',report])
records=[{'path':path.relative_to(root).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths]
worktree=Path('C:/Users/yinha/.codex/worktrees/recovery-r05-generation-review-1-deferred/dianzi')
status=subprocess.check_output(['git','status','--porcelain'],cwd=worktree,text=True)
manifest={'captured_at':datetime.datetime.now(zone).isoformat(timespec='seconds'),'head':'31c2866ff19227e5f6ee24f1f966660c0d4ba383','tree':'c0c4659b8c1c392eba67c22d15939bae6032bd36','conclusion':'two Must fixes closed within generation/shared POST technical scope; no product live or stage acceptance','source_status_porcelain':status,'records':records,'resource_state':'all exec test/static/CLI processes complete; socket/server cleanup and thread joins passed; no DB or background service created; clean worktrees and external coverage runtimes retained for reproducibility'}
(new/'artifact_manifest_final_31.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'captured_at':manifest['captured_at'],'files':len(records),'clean':not status,'report_sha256':records[-1]['sha256'],'raw_coverage':raw}))
