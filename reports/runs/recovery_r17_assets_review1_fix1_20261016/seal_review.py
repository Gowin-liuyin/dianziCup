"""封存独立报告与原始证据，只 stage 当前审查允许的文件。"""
import hashlib
import json
import pathlib
import subprocess
from datetime import datetime, timezone, timedelta

ROOT = pathlib.Path('D:/wt/r17-assets-review1-fix1')
PREFIX = 'reports/runs/recovery_r17_assets_review1_fix1_20261016'
RUN = ROOT / PREFIX
REPORT = 'reports/reviews/recovery/G-E-R17-assets-workbench-review-1-recheck.md'
CODE = 'a25fd81c50f0ea14f44e7fda2c3edac5cab74d48'
MATERIAL = 'f9f041056ac717c6be2287a4ad97058538adce66'
EXCLUDED = {'raw_manifest.json', 'raw_manifest.sha256', 'sealed_byte_proof.json', 'seal_check.log'}
now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
sha = lambda value: hashlib.sha256(value).hexdigest()
def git(*arguments):
    return subprocess.check_output(['git', *arguments], cwd=ROOT)
def write(name, value):
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

started = now()
files = [file for file in sorted(RUN.rglob('*')) if file.is_file() and file.name not in EXCLUDED]
entries = [{'path': file.relative_to(ROOT).as_posix(), 'bytes': file.stat().st_size, 'sha256': sha(file.read_bytes())} for file in files]
write('raw_manifest.json', {'recorded_at': started, 'reviewed_code': CODE, 'reviewed_material': MATERIAL, 'scope': 'independent frontend review; all inputs synthetic, no real private asset data', 'files': entries})
manifest_raw = (RUN / 'raw_manifest.json').read_bytes()
(RUN / 'raw_manifest.sha256').write_text(sha(manifest_raw) + '  raw_manifest.json\n', encoding='utf-8')
git('-c', 'core.autocrlf=false', 'add', '--', REPORT, PREFIX)
verified = []
for entry in entries + [{'path': REPORT, 'bytes': (ROOT / REPORT).stat().st_size, 'sha256': sha((ROOT / REPORT).read_bytes())}, {'path': PREFIX + '/raw_manifest.json', 'bytes': len(manifest_raw), 'sha256': sha(manifest_raw)}, {'path': PREFIX + '/raw_manifest.sha256', 'bytes': (RUN / 'raw_manifest.sha256').stat().st_size, 'sha256': sha((RUN / 'raw_manifest.sha256').read_bytes())}]:
    blob = git('show', ':0:' + entry['path']); work = (ROOT / entry['path']).read_bytes()
    verified.append({**entry, 'git_index_sha256': sha(blob), 'git_index_bytes': len(blob), 'working_bytes_equal_index': blob == work, 'manifest_equal_work_and_index': sha(blob) == sha(work) == entry['sha256'] and len(blob) == entry['bytes']})
changed = [path for path in git('diff', '--cached', '--name-only', '-z').decode().split('\0') if path]
unexpected = [path for path in changed if path != REPORT and not path.startswith(PREFIX + '/')]
source_diff = git('diff', MATERIAL, '--', 'frontend', 'backend', 'contracts', 'progress', 'docs', '.gitattributes')
checks = {}
for name, arguments in [('review_code_style', ['diff', '--cached', '--check', '--', REPORT, PREFIX + '/*.py', PREFIX + '/*.ps1', PREFIX + '/*.cjs']), ('raw_all_whitespace', ['diff', '--cached', '--check'])]:
    result = subprocess.run(['git', *arguments], cwd=ROOT, capture_output=True)
    checks[name] = {'command': ['git', *arguments], 'cwd': str(ROOT), 'exit_code': result.returncode, 'output': (result.stdout + result.stderr).decode(errors='replace')}
write('sealed_byte_proof.json', {'started_at': started, 'sealed_at': now(), 'review_head': git('rev-parse', 'HEAD').decode().strip(), 'reviewed_code': CODE, 'reviewed_material': MATERIAL, 'report': REPORT, 'report_sha256': sha((ROOT / REPORT).read_bytes()), 'raw_manifest_sha256': sha(manifest_raw), 'raw_evidence_files': len(entries), 'verified_work_and_index_files': len(verified), 'mismatches': sum(not entry['manifest_equal_work_and_index'] for entry in verified), 'source_or_contract_diff_bytes': len(source_diff), 'unexpected_staged_paths': unexpected, 'stage_command': ['git', '-c', 'core.autocrlf=false', 'add', '--', REPORT, PREFIX], 'raw_policy': 'Preserve raw bytes. No .gitattributes edit, no raw clipping, no global check suppression. Full raw whitespace check may flag original CLI error snippets; source/report check excludes raw output intentionally.', 'checks': checks, 'files': verified})
git('-c', 'core.autocrlf=false', 'add', '--', PREFIX + '/sealed_byte_proof.json')
proof_raw = (RUN / 'sealed_byte_proof.json').read_bytes()
assert git('show', ':0:' + PREFIX + '/sealed_byte_proof.json') == proof_raw
assert not unexpected and not source_diff and all(entry['manifest_equal_work_and_index'] for entry in verified)
result = {'recorded_at': now(), 'report_sha256': sha((ROOT / REPORT).read_bytes()), 'raw_manifest_sha256': sha(manifest_raw), 'sealed_byte_proof_sha256': sha(proof_raw), 'raw_files': len(entries), 'work_and_index_verified': len(verified), 'source_diff_bytes': len(source_diff), 'unexpected_paths': unexpected, 'style_exit': checks['review_code_style']['exit_code'], 'raw_whitespace_exit': checks['raw_all_whitespace']['exit_code'], 'verdict': 'Ship: M01 closed, frontend slice only'}
print(json.dumps(result, ensure_ascii=False))
