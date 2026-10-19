"""Write source crosschecks and a post-exit identity audit without mutating source."""

import json
import os
import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).parent
sys.path.insert(0, str(RUN))
import index_support as support

if os.name != 'nt':
    current = support.linux_snapshot()
    expected = []
    for directory in (RUN, RUN / 'attempt2', RUN / 'attempt3', RUN / 'supplement'):
        value = json.loads((directory / 'linux_resources.json').read_text())
        expected.extend(value['peak_chain'] + value['control_chain'] + value['cleanup_exact_owned_identities'])
    unique = {(row['pid'], row['birth_clock_ticks'], row['pid_namespace']): row for row in expected}
    remaining = [row for key, row in unique.items() if row['pid'] in current and (current[row['pid']]['pid'], current[row['pid']]['birth_clock_ticks'], current[row['pid']]['pid_namespace']) == key]
    (RUN / 'postexit_linux.json').write_text(json.dumps({'recorded_at': support.now(), 'audited_identity_count': len(unique), 'remaining_owned_processes': remaining, 'ownership': 'exact PID + birth ticks + namespace; inaccessible wrapper namespace retained explicitly; no Docker/runc adopted'}, indent=2) + '\n')
    raise SystemExit(bool(remaining))

ROOT = Path('D:/dianzi')
queries = [
    ('public_mount', 'build_public_extension_router|include_router', ['backend/src/ai_intel/api/app.py']),
    ('public_reader', 'PublicExtensionReadService|reader\.(search_vulns|get_vuln|list_sources|get_task_result)|def get_task_result|public task owner|503', ['backend/src/ai_intel/api/public_extension_routes.py', 'backend/src/ai_intel/api/public_extension_reads.py']),
    ('workflow_graph_and_reads', 'build_investigation_graph|runtime.run_role|AgentRole.ENRICHER|KnowledgeReadService|GetAdvisoryCall|GetInventoryCall|FindChangesCall|PostgresReadToolAdapter|enrichment_write_adapter_not_configured', ['backend/src/ai_intel/investigation/workflow_service.py']),
    ('bridge_callers', 'build_source_report_reader|read_enrichment_source_reports|StructuredFactProofReader', ['backend/src']),
    ('worker_final_guard', 'make_revalidation_job_handlers|execute_job|handler.handler|handler.completion_guard|guard_completed_fan_in|def guard_completion|return DetachedJobHandler|REVALIDATION_CHANGE_JOB_TYPE|REASSESSMENT_JOB_TYPE', ['backend/src/ai_intel/workers/runtime.py', 'backend/src/ai_intel/workers/executor.py', 'backend/src/ai_intel/revalidation/runtime_policy.py']),
    ('change_projection', 'knowledge_change|KNOWLEDGE_CHANGE_JOB_TYPE|GRAPH_APPLY_JOB_TYPE|build_graph_apply_handler|build_projection_job_handlers|handlers.update', ['backend/src/ai_intel/retrieval/runtime_policy.py', 'backend/src/ai_intel/knowledge/graph_projection.py', 'backend/src/ai_intel/workers/runtime.py']),
    ('execute_owned_symbol_absent', 'execute_owned', ['backend/src']),
]
rows = []
for label, pattern, paths in queries:
    command = ['rg', '-n', pattern, *paths]
    start = support.now()
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=20)
    (RUN / (label + '.source.stdout.log')).write_bytes(result.stdout)
    (RUN / (label + '.source.stderr.log')).write_bytes(result.stderr)
    receipt = {'command': command, 'cwd': str(ROOT), 'started_at': start, 'ended_at': support.now(), 'exit_code': result.returncode, 'expected_no_match': label == 'execute_owned_symbol_absent', 'timeout_seconds': 20}
    (RUN / (label + '.source.command.json')).write_text(json.dumps(receipt, indent=2) + '\n')
    rows.append(receipt)
(RUN / 'source_crosschecks.json').write_text(json.dumps(rows, indent=2) + '\n')
sys.path.insert(0, 'D:/wt/r14-qualified-root-integration/reports/runs/r14_qualified_root_integration_20261017')
import process_metadata as metadata
expected = []
for directory in (RUN / 'attempt3', RUN / 'supplement'):
    value = json.loads((directory / 'sequence.command.json').read_text())
    expected.extend(value['windows_peak_chain'] + value['control_chain'])
unique = {(row['pid'], row['birth_utc']): row for row in expected}
remaining = []
for key, row in unique.items():
    try:
        if metadata.identity(row['pid']) == {'pid': row['pid'], 'birth_utc': row['birth_utc']}:
            remaining.append(row)
    except OSError:
        continue
(RUN / 'postexit_windows.json').write_text(json.dumps({'recorded_at': support.now(), 'audited_identity_count': len(unique), 'remaining_owned_processes': remaining, 'ownership': 'exact PID + Windows creation time; reused PID excluded'}, indent=2) + '\n')
command = ['wsl.exe', '-d', 'Ubuntu-22.04', '--exec', '/usr/bin/python3', '/mnt/d/dianzi/reports/runs/root_batch13_index_20261017/finalize_support.py']
start = support.now()
result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=20)
(RUN / 'postexit.command.json').write_text(json.dumps({'command': command, 'started_at': start, 'ended_at': support.now(), 'exit_code': result.returncode, 'timeout_seconds': 20}, indent=2) + '\n')
(RUN / 'postexit.stdout.log').write_bytes(result.stdout)
(RUN / 'postexit.stderr.log').write_bytes(result.stderr)
before = json.loads((RUN / 'source_before.json').read_text())
after = json.loads((RUN / 'source_after.json').read_text())
stable = before['files'] == after['files'] and before['tree_sha256'] == after['tree_sha256']
cli = []
for directory in (RUN, RUN / 'attempt2', RUN / 'attempt3', RUN / 'supplement'):
    cli.extend(json.loads(path.read_text()) for path in directory.glob('*.command.json') if json.loads(path.read_text()).get('command', [''])[0] == support.TOOL)
value = {'recorded_at': support.now(), 'source_stable': stable, 'source_tree_sha256': before['tree_sha256'], 'python_file_count': before['python_file_count'], 'logged_cli_command_count': len(cli), 'logged_cli_elapsed_seconds': sum(row['elapsed_seconds'] for row in cli), 'max_logged_cli_elapsed_seconds': max(row['elapsed_seconds'] for row in cli), 'cli_budget_seconds': 180, 'exploratory_cli_help_shell_elapsed_upper_seconds': 5.5371242000000005, 'remaining_owned_windows_processes': len(remaining), 'postexit_linux_command_exit': result.returncode, 'business_tests_executed': 0, 'unit': 'not_run', 'integration': 'not_run', 'live': 'not_run', 'manual': 'not_run', 'acceptance': 'not_signed'}
(RUN / 'delivery_receipt.json').write_text(json.dumps(value, indent=2) + '\n')
print(json.dumps(value))
raise SystemExit(bool(remaining or result.returncode or not stable))
