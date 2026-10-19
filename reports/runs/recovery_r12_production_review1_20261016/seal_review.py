"""Seal review outputs without source mutation or a circular commit identity."""

import hashlib
import json
import subprocess

from review_checks import CODE, MATERIAL, ROOT, RUN, now, scan, write_json

report = ROOT / 'reports/reviews/recovery/G-D-R12-production-migration-review-1.md'
content = report.read_text(encoding='utf-8')
content = content.replace('真实 10001 条事实', '真实 10001 个事实候选组合行')
content = content.replace('实际10001条事实超10000容量', '实际10001个合法事件/证据/claim组合行超10000查询容量')
content = content.replace('往 OS 写10001条', '往 OS 写10001个投影')
report.write_text(content, encoding='utf-8', newline='\n')
scan()
members = []
for path in sorted([p for p in RUN.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc' and p.name != 'review_manifest.json'] + [report]):
    raw = path.read_bytes()
    members.append({'path': path.relative_to(ROOT).as_posix(), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == MATERIAL
assert not subprocess.check_output(['git', 'diff', '--name-only'], cwd=ROOT).strip()
write_json(RUN / 'review_manifest.json', {'created_at': now(), 'baseline': 'b502b7ea4a2ffdeca24b8edc7fa8a33cc0980457', 'code': CODE, 'material': MATERIAL, 'review_commit': None, 'report_sha256': hashlib.sha256(report.read_bytes()).hexdigest(), 'members': members, 'excluded': ['__pycache__', '*.pyc', 'model/tool caches', 'secret reference', 'holdout'], 'verdict': 'Ship limited to four-file production migration slice'})
manifest = RUN / 'review_manifest.json'
final = json.loads(manifest.read_text())
assert all((ROOT / member['path']).stat().st_size == member['bytes'] and hashlib.sha256((ROOT / member['path']).read_bytes()).hexdigest() == member['sha256'] for member in final['members'])
print(json.dumps({'report_sha256': final['report_sha256'], 'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(), 'members': len(members), 'verdict': final['verdict']}))
