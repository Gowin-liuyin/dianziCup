"""Seal review evidence and scan only explicitly authorized test credentials."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from review_runner import DATABASE, RUN, TARGET, WT, now, read_private, secrets

REPORT = Path('D:/dianzi/reports/reviews/recovery/G-B-R04-sources-review-1.md')


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def main() -> None:
    started = now()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=WT, text=True).strip()
    assert head == TARGET
    status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=WT, text=True)
    assert status == ''
    values = secrets(read_private())
    full_patterns = [value.encode() for value in values if value]
    password = values[1].encode()
    fragment_patterns = {password[index:index + 8] for index in range(len(password) - 7)}
    redacted_masked_urls = []
    for path in sorted(RUN.iterdir()):
        if path.suffix in {'.log', '.xml'}:
            original = path.read_text(encoding='utf-8')
            redacted, count = re.subn(r'postgresql(?:\+psycopg)?://[^\s)<>]+',
                                     '[REDACTED test database locator]', original)
            if count:
                path.write_text(redacted, encoding='utf-8')
                redacted_masked_urls.append({'file': path.name, 'replacements': count})
    tracked_sources = subprocess.check_output(
        ['git', 'diff', '--name-only', '2522b3a..HEAD', '--', 'backend/src',
         'backend/migrations', 'backend/tests', 'fixtures/recorded'], cwd=WT, text=True).splitlines()
    sources = []
    scan_candidates = [(path, path.read_bytes()) for path in sorted(RUN.iterdir())
                       if path.is_file() and path.name not in
                       {'manifest.json', 'credential_scan.json', 'seal.command.json'}]
    scan_candidates.append((REPORT, REPORT.read_bytes()))
    for relative in tracked_sources:
        blob = subprocess.check_output(['git', 'show', f'{TARGET}:{relative}'], cwd=WT)
        sources.append({'path': relative, 'git_blob_sha256': digest(blob), 'bytes': len(blob)})
        scan_candidates.append((WT / relative, blob))
    findings = []
    generic = re.compile(rb'(?:ghp_[A-Za-z0-9]{30,}|sk-proj-[A-Za-z0-9_-]{20,}|'
                         rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
    for path, body in scan_candidates:
        full_count = sum(body.count(pattern) for pattern in full_patterns)
        fragment_count = sum(body.count(pattern) for pattern in fragment_patterns)
        generic_count = len(generic.findall(body))
        if full_count or fragment_count or generic_count:
            findings.append({'path': str(path), 'actual_credential_full_matches': full_count,
                             'actual_credential_8byte_matches': fragment_count,
                             'generic_secret_matches': generic_count})
    scan = {'started_at': started, 'ended_at': now(),
            'scope': 'own evidence/report plus exact frozen changed source/test/recorded blobs',
            'files_scanned': len(scan_candidates), 'test_credential_only': True,
            'real_product_credentials_read': False, 'full_pattern_count': len(full_patterns),
            'consecutive_8byte_pattern_count': len(fragment_patterns), 'findings': findings,
            'masked_test_locator_redactions': redacted_masked_urls,
            'exit_code': 0 if not findings else 1, 'secret_values_written': False}
    (RUN / 'credential_scan.json').write_text(json.dumps(scan, indent=2), encoding='utf-8')
    contracts = ['AGENTS.md', 'docs/plan/00_execution_map.md',
        'docs/plan/11_full_delivery_recovery_20261014.md',
        'docs/plan/12_recovery_task_cards_20261014.md', 'docs/plan/03_data_contracts.md',
        'docs/plan/05_api_and_tool_contracts.md', 'docs/tasks/T05_persistence_and_raw_store.md',
        'docs/tasks/T09_document_parsing.md', 'docs/tasks/T10_cve_nvd_connectors.md',
        'docs/tasks/T12_vendor_blog_connectors.md',
        'docs/tasks/T13_community_repository_connectors.md', 'docs/tasks/T14_academic_connector.md',
        'docs/tasks/T40_frontend_shell.md',
        'docs/decisions/CR-R04-R04_source_persistence.md', 'progress/task_state.json',
        'progress/context_handoff.md', 'reports/tasks/R04-NVD-source-schema.md']
    manifest = {'started_at': started, 'ended_at': now(), 'status': 'needs_changes',
        'head': head, 'tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'],
             cwd=WT, text=True).strip(), 'baseline': subprocess.check_output(
             ['git', 'rev-parse', '2522b3a'], cwd=WT, text=True).strip(),
        'worktree': str(WT), 'branch': 'codex/recovery-r04-sources-review-1',
        'worktree_status_porcelain': status, 'own_database': DATABASE, 'own_database_released': True,
        'source_blobs': sources,
        'authority_document_hashes': [{'path': relative, 'sha256': digest((WT / relative).read_bytes())}
             for relative in contracts],
        'report': {'path': str(REPORT), 'sha256': digest(REPORT.read_bytes())},
        'evidence_files': [{'path': path.name, 'sha256': digest(path.read_bytes()),
                            'bytes': path.stat().st_size} for path in sorted(RUN.iterdir())
                            if path.is_file() and path.name not in {'manifest.json', 'seal.command.json'}],
        'credential_scan_passed': not findings, 'stage_or_whole_card_accepted': False,
        'paid_model_calls': 0, 'source_gets_by_reviewer': 0,
        'business_files_modified': [], 'progress_or_contracts_modified': []}
    (RUN / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    receipt = {'command': ['D:/dianzi/backend/.venv/Scripts/python.exe', str(Path(__file__))],
        'cwd': str(WT), 'started_at': started, 'ended_at': now(), 'head': TARGET,
        'exit_code': 0 if not findings else 1, 'files_scanned': len(scan_candidates),
        'test_credential_full_or_8byte_findings': len(findings),
        'raw_file_manifest_sha256': digest((RUN / 'manifest.json').read_bytes())}
    (RUN / 'seal.command.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt))
    if findings:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
