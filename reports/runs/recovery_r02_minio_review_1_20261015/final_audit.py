"""Finalize only reviewer artifacts after an in-memory known-secret scan and clean WT check."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

from run_review import ROOT, RUN, SHA, WT, now, private


def main() -> int:
    checked_at = now()
    report = ROOT / 'reports/reviews/recovery/G-A-R02-minio-integrated-review-1.md'
    report_value = report.read_text(encoding='utf-8')
    report_value = report_value.replace(
        '写作结束与最后clean/秘密扫描见专属最终收据（实际后续记录，不回填测试起点）。',
        f'写作结束：{checked_at}；最后clean/秘密扫描见专属最终收据（实际后续记录，不回填测试起点）。')
    report.write_text(report_value, encoding='utf-8')
    pg = private('/tmp/dianzi-r02_knowledge_20261015/connection.json')
    objects = private('/tmp/dianzi-minio-r02-20261015/private/connection.json')
    fragments = {objects['secret_key'], unquote(urlsplit(pg['TEST_DATABASE_URL']).password or '')}
    fragments.discard('')
    fragments.update(value[index:index+8] for value in list(fragments) for index in range(len(value)-7))
    fragments.update((objects['access_key'], pg['TEST_DATABASE_URL']))
    paths = [report, *(path for path in RUN.rglob('*') if path.is_file()
                       and path.name not in {'final_audit.json', 'artifact_manifest.json'})]
    match_paths = [str(path.relative_to(ROOT)).replace('\\', '/') for path in paths
                   if any(value.encode() in path.read_bytes() for value in fragments)]
    actual_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=WT, text=True).strip()
    clean = subprocess.check_output(['git', 'status', '--porcelain'], cwd=WT, text=True).strip() == ''
    record = {'checked_at': checked_at, 'candidate_sha': actual_sha,
              'candidate_unchanged': actual_sha == SHA, 'worktree_clean': clean,
              'known_secret_match_paths': match_paths,
              'scan_scope': 'only this review report and owned run; full DSN/access identifier; full and all 8-character password/secret-key fragments; native random-session full/fragment checks separately recorded',
              'business_files_changed': [], 'commits_or_pushes': [],
              'database_scope': 'r02_knowledge_20261015/head0009_enrichment_results',
              'command': ['C:/Users/yinha/.codex/tmp/r02-minio-review1-venv/Scripts/python.exe', str(Path(__file__).resolve())]}
    (RUN/'final_audit.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    artifact_paths = [report, *(path for path in RUN.rglob('*') if path.is_file()
                               and path.name != 'artifact_manifest.json')]
    manifest = [{'path': str(path.relative_to(ROOT)).replace('\\', '/'),
                 'size_bytes': path.stat().st_size,
                 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                for path in sorted(artifact_paths)]
    (RUN/'artifact_manifest.json').write_text(json.dumps({'checked_at': checked_at,
                                                        'artifacts': manifest}, indent=2), encoding='utf-8')
    print(json.dumps(record))
    print(json.dumps({'manifest': 'reports/runs/recovery_r02_minio_review_1_20261015/artifact_manifest.json',
                      'artifact_count_excluding_manifest_itself': len(manifest)}))
    return 0 if actual_sha == SHA and clean and not match_paths else 1


if __name__ == '__main__':
    raise SystemExit(main())
