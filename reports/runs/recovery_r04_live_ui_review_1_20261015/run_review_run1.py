"""Run bounded independent browser observation and redact identity before persistence."""
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
FRONTEND = Path.home() / '.codex/worktrees/r04-real-pipeline/dianzi/frontend'
EXPECTED_SHA = '7184dc63525ae3e8ea439ec64fc03dfaa629f7a8'


def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')


def main():
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=FRONTEND, text=True).strip()
    tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=FRONTEND, text=True).strip()
    if sha != EXPECTED_SHA:
        raise RuntimeError('frozen source SHA mismatch')
    if (RUN / 'browser.stdout.json').exists():
        raise FileExistsError('evidence run cannot be overwritten')
    environment = dict(os.environ)
    environment['PLAYWRIGHT_BROWSERS_PATH'] = str(Path.home() / '.codex/cache/dianzi/r01_playwright_1248')
    secrets = [environment[name] for name in ('DIANZI_E2E_USERNAME', 'DIANZI_E2E_PASSWORD')]
    fragments = {value.encode() for value in secrets}
    for value in secrets:
        if len(value) >= 8:
            fragments.update(value[index:index+8].encode() for index in range(len(value)-7))
    command = ['node', str(RUN / 'live_browser_review.mjs')]
    started = now()
    completed = subprocess.run(command, cwd=FRONTEND, env=environment, capture_output=True, timeout=300)

    def redact(content):
        for fragment in sorted(fragments, key=len, reverse=True):
            content = content.replace(fragment, b'[redacted test identity]')
        return content

    (RUN / 'browser.stdout.json').write_bytes(redact(completed.stdout))
    (RUN / 'browser.stderr.log').write_bytes(redact(completed.stderr))
    receipt = {'command':command,'cwd':str(FRONTEND),'started_at':started,'ended_at':now(),'exit_code':completed.returncode,'code_sha':sha,'tree_sha':tree,'browser':'Chromium headless shell 1248','trace':'off','video':'off','automatic_screenshots':'off','storage_state_saved':False,'api_response_overrides':False}
    (RUN / 'command.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    hits = []
    files = []
    for file in RUN.rglob('*'):
        if not file.is_file():
            continue
        content = file.read_bytes()
        count = sum(fragment in content for fragment in fragments)
        files.append({'path':str(file),'size_bytes':len(content),'actual_secret_fragment_hits':count})
        if count:
            hits.append(str(file))
    manifest = {'scanned_at':now(),'scope':'all own run files including PNG binary; both actual identity strings and every >=8-character contiguous fragment','files':files,'hit_count':len(hits),'hits':hits,'secrets_printed':False}
    (RUN / 'credential_scan_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'exit_code':completed.returncode,'secret_scan_hits':len(hits),'evidence_file':str(RUN / 'browser.stdout.json')}))
    return completed.returncode if not hits else 2


if __name__ == '__main__':
    raise SystemExit(main())
