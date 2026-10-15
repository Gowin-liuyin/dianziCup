from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path('C:/Users/yinha/.codex/worktrees/recovery-r05-generation-review-1/dianzi')
RUN = pathlib.Path(__file__).resolve().parent
ZONE = datetime.timezone(datetime.timedelta(hours=8))
FILES = [
 'AGENTS.md', 'docs/plan/00_execution_map.md', 'docs/plan/02_architecture.md', 'docs/plan/03_data_contracts.md',
 'docs/plan/04_workflows_and_algorithms.md', 'docs/plan/05_api_and_tool_contracts.md', 'docs/plan/06_testing_and_evaluation.md',
 'docs/plan/07_sources_and_resources.md', 'docs/plan/09_operations_delivery.md', 'docs/plan/11_full_delivery_recovery_20261014.md',
 'docs/plan/12_recovery_task_cards_20261014.md', 'docs/tasks/T18_model_clients.md', 'docs/tasks/T20_claim_extraction.md',
 'docs/tasks/T30_hybrid_retrieval.md', 'docs/tasks/T31_grounded_qa_baseline.md', 'docs/tasks/T43_qa_agents_recommendations_ui.md',
 'docs/decisions/CR-R04-R05_model_post.md', 'contracts/task_manifest.json', 'progress/task_state.json', 'progress/context_handoff.md',
 'backend/src/ai_intel/infrastructure/models/generation.py', 'backend/src/ai_intel/infrastructure/models/clients.py',
 'backend/src/ai_intel/infrastructure/models/json_output.py', 'backend/src/ai_intel/infrastructure/network.py',
 'backend/src/ai_intel/infrastructure/http_transport.py', 'config/models/providers.yaml', 'backend/pyproject.toml', 'backend/uv.lock',
 'backend/tests/unit/test_r05_generation.py', 'backend/tests/contract/test_r05_generation_wire.py',
 'backend/tests/contract/test_t18_model_clients.py', 'backend/tests/integration/test_r05_generation_http.py',
 'backend/tests/security/test_r05_http_post.py', 'backend/tests/security/test_r05_transport_timeouts.py',
 'backend/tests/security/test_r03_network_transport.py', 'backend/tests/contract/test_t08_network_redirects.py',
]

def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, check=True).stdout

def digest(value):
    return hashlib.sha256(value).hexdigest()

records = []
for name in FILES:
    path = ROOT / name
    captured = path.read_bytes()
    blob = git('show', 'HEAD:' + name)
    records.append({'path': name, 'captured_sha256': digest(captured), 'git_blob_sha1': git('rev-parse', 'HEAD:' + name).decode().strip(), 'git_blob_content_sha256': digest(blob), 'captured_matches_git_blob_bytes': captured == blob, 'captured_bytes': len(captured), 'git_blob_bytes': len(blob)})
manifest = {'captured_at': datetime.datetime.now(ZONE).isoformat(timespec='seconds'), 'worktree': str(ROOT), 'head': git('rev-parse', 'HEAD').decode().strip(), 'tree': git('rev-parse', 'HEAD^{tree}').decode().strip(), 'status_porcelain': git('status', '--porcelain').decode(), 'files': records}
(RUN / 'fixed_source_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

results = []
for path in sorted(RUN.glob('*.xml')):
    if 'coverage' in path.name:
        continue
    document = ET.parse(path).getroot()
    suites = [document] if document.tag == 'testsuite' else list(document.findall('testsuite'))
    results.append({'path': path.name, **{key: sum(int(suite.attrib.get(key, '0')) for suite in suites) for key in ('tests', 'failures', 'errors', 'skipped')}, 'testcases': [case.attrib.get('classname', '') + '::' + case.attrib.get('name', '') for suite in suites for case in suite.findall('testcase')]})
(RUN / 'junit_summary.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')

spec = importlib.util.spec_from_file_location('review_scan_source', ROOT / 'scripts/security_scan.py')
scanner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scanner
spec.loader.exec_module(scanner)
scan_paths = [ROOT / name for name in FILES if name.startswith(('backend/src/', 'backend/tests/'))]
scan_paths.extend(path for path in RUN.iterdir() if path.is_file() and path.suffix in {'.py', '.json', '.log', '.xml', '.txt'})
findings = []
for path in scan_paths:
    if path.name in {'artifact_shape_scan.json', 'artifact_manifest.json'}:
        continue
    raw = path.read_bytes()
    content = raw.decode('utf-8', errors='replace')
    for pattern_id, pattern in scanner.PATTERNS.items():
        for match in pattern.finditer(content):
            value = match.group(0)
            classified = 'synthetic' in value.casefold() or 'fixture' in value.casefold()
            findings.append({'path': str(path), 'line': content[:match.start()].count('\n')+1, 'pattern_id': pattern_id, 'match_sha256': digest(value.encode()), 'category': 'synthetic_test_probe' if classified else 'requires_manual_review'})
scan = {'captured_at': datetime.datetime.now(ZONE).isoformat(timespec='seconds'), 'scope': 'fixed reviewed code/tests and this review artifacts only; no secret store or holdout', 'credential_shape_patterns': list(scanner.PATTERNS), 'actual_product_credential_exact_scan': 'not_run; reviewer never read product credentials', 'files_scanned': len(scan_paths), 'findings': findings}
(RUN / 'artifact_shape_scan.json').write_text(json.dumps(scan, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'head': manifest['head'], 'clean': not manifest['status_porcelain'], 'files': len(records), 'junit': [{k: v for k, v in row.items() if k != 'testcases'} for row in results], 'scan_files': len(scan_paths), 'shape_findings': len(findings), 'unclassified': [finding for finding in findings if finding['category'] == 'requires_manual_review']}, ensure_ascii=False))
