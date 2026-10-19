"""Attach actual execution windows and seal reviewer artifacts after reading JUnit."""

import datetime
import hashlib
import json
from pathlib import Path
import subprocess

RUN = Path(__file__).resolve().parent
REPORT = Path('D:/dianzi/reports/reviews/recovery/G-C-R10-pg-evidence-graph-review-1.md')
ROOT = Path('D:/wt/r10-graph-review1')
labels = ['r10_pure', 'r10_pg_original', 'r10_related', 'r10_pg_independent', 'r10_pg_independent_extended', 'r10_pg_load', 'r10_pg_load_exact', 'r10_ruff', 'r10_format', 'r10_mypy']
rows = []
for label in labels:
    receipt = json.loads((RUN / (label + '.json')).read_text(encoding='utf-8'))
    rows.append('| `' + label + '` | ' + receipt['started_at'] + ' | ' + receipt['finished_at'] + ' | ' + str(receipt['exit_code']) + ' |')
table = '\n\n实际 +08:00 执行窗口如下；完整 argv 保持在同名 command receipt，不记录 DSN。\n\n| label | 开始 | 结束 | exit |\n|---|---|---|---|\n' + '\n'.join(rows) + '\n\n'
report = REPORT.read_text(encoding='utf-8')
marker = '\n原冻结测试和相关回归合计独立通过'
assert marker in report and '实际 +08:00 执行窗口如下' not in report
report = report.replace(marker, table + marker)
REPORT.write_text(report, encoding='utf-8')
manifest = {'recorded_at': datetime.datetime.now().astimezone().isoformat(), 'code_sha': 'b0b7a5b856cc38862f64c01565309564d67c34c0', 'material_sha': '16803ce6be9ad6adb6d89f46c594cfa420190c24', 'verdict': 'needs_changes', 'files': []}
for path in sorted([p for p in RUN.iterdir() if p.is_file() and p.name != 'reviewer_artifact_manifest.json'] + [REPORT]):
    content = path.read_bytes()
    manifest['files'].append({'path': str(path), 'raw_bytes': len(content), 'raw_sha256': hashlib.sha256(content).hexdigest()})
manifest['review_worktree_status'] = subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True)
assert manifest['review_worktree_status'] == ''
(RUN / 'reviewer_artifact_manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'verdict': manifest['verdict'], 'files_sealed': len(manifest['files']), 'report_bytes': REPORT.stat().st_size, 'report_sha256': hashlib.sha256(REPORT.read_bytes()).hexdigest(), 'worktree_status_clean': True}, indent=2))
