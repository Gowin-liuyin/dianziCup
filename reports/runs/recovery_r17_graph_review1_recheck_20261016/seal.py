"""封存自有审查证据，不重写作者文件或已存在的原始日志。"""
from __future__ import annotations
import hashlib
import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path('D:/wt/r17-graph-recheck1')
RUN=ROOT/'reports/runs/recovery_r17_graph_review1_recheck_20261016'
REPORT=ROOT/'reports/reviews/recovery/G-E-R17-evidence-graph-review-1-recheck.md'
EXCLUDE={'artifact_manifest.json','artifact_manifest.sha256','seal.stdout.log','seal.stderr.log','seal-refresh.stdout.log','seal-refresh.stderr.log'}
def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
def entry(path: Path) -> dict[str, object]:
    content=path.read_bytes()
    item={'path':path.relative_to(ROOT).as_posix(),'bytes':len(content),'raw_sha256':sha(content)}
    if b'\x00' not in content:
        try:
            content.decode('utf-8')
        except UnicodeDecodeError:
            pass
        else:
            item['lf_sha256']=sha(content.replace(b'\r\n',b'\n'));item['crlf_count']=content.count(b'\r\n')
    return item
status=subprocess.check_output(['git','status','--short'],cwd=ROOT).decode('utf-8')
assert not any(line[:2].strip() and not line.startswith('??') for line in status.splitlines()), status
report=REPORT.read_text(encoding='utf-8')
assert all(line==line.rstrip() for line in report.splitlines()), 'report contains trailing whitespace'
audit=json.loads((RUN/'audit.json').read_text(encoding='utf-8'))
process=json.loads((RUN/'process-after.json').read_text(encoding='utf-8-sig'))
assert not process['listeners']
manifest={'schema_version':1,'recorded_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),'review_sha':'none','reviewed_sha':audit['reviewed_sha'],'reviewed_tree':audit['reviewed_tree'],'source_freeze':audit['source_sha'],'verdict':'Ship current pointer fix; original Must1 closed','source':audit['source'],'author_manifest':audit['author_manifest'],'source_author_artifact_count':len(audit['owned']),'author_raw_changed':False,'artifact_count':0,'artifacts':[entry(path) for path in sorted([REPORT]+[p for p in RUN.rglob('*') if p.is_file() and (p.parent!=RUN or p.name not in EXCLUDE)])],'excluded_self_referential_files':sorted(EXCLUDE),'git_status':status}
manifest['artifact_count']=len(manifest['artifacts'])
content=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
(RUN/'artifact_manifest.json').write_bytes(content)
(RUN/'artifact_manifest.sha256').write_text(sha(content)+'  artifact_manifest.json\n',encoding='utf-8')
print(json.dumps({'artifact_count':manifest['artifact_count'],'manifest_body_sha256':sha(content),'source_files':len(manifest['source']),'reviewed_sha':manifest['reviewed_sha'],'review_sha':'none'},ensure_ascii=False))
