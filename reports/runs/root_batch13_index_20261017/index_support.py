"""Bounded read-only index evidence for the current Root workspace."""

import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).parent
if len(sys.argv) > 2 and sys.argv[1] in {'windows', 'linux'}:
    RUN = Path(sys.argv[2])
ROOT = Path('/mnt/d/dianzi') if os.name != 'nt' else Path('D:/dianzi')
TOOL = '/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp'
PROJECT = 'root-batch13-20261017'
CACHE = '/tmp/dianzi-cbm-root-batch13-20261017'


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='milliseconds')


def freeze(label):
    rows = []
    for directory in ('backend/src', 'backend/migrations'):
        for path in sorted((ROOT / directory).rglob('*.py')):
            rows.append({'path': path.relative_to(ROOT).as_posix(), 'raw_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    rows.sort(key=lambda row: row['path'])
    canonical = ''.join(row['path'] + '\0' + row['raw_sha256'] + '\n' for row in rows).encode()
    value = {'recorded_at': now(), 'scope': ['backend/src/**/*.py', 'backend/migrations/**/*.py'], 'canonical_format': 'UTF-8 sorted repo-relative POSIX path + NUL + lowercase raw SHA256 + LF', 'python_file_count': len(rows), 'tree_sha256': hashlib.sha256(canonical).hexdigest(), 'files': rows, 'head_context_only': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()}
    (RUN / ('source_' + label + '.json')).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    return value


def linux_snapshot():
    rows = {}
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            raw = path.read_text()
            tail = raw.rsplit(')', 1)[1].split()
            pid = int(path.parent.name)
            try:
                namespace = os.readlink(path.parent / 'ns/pid')
            except OSError as error:
                namespace = 'unreadable:' + type(error).__name__
            rows[pid] = {'pid': pid, 'parent_pid': int(tail[1]), 'birth_clock_ticks': int(tail[19]), 'state': tail[0], 'name': raw.split('(', 1)[1].rsplit(')', 1)[0], 'pid_namespace': namespace}
        except (OSError, ValueError):
            continue
    return rows


def linux_run():
    initial = linux_snapshot()
    identity = initial[os.getpid()]
    chain = [identity]
    while identity['parent_pid'] > 1 and identity['parent_pid'] in initial:
        parent = initial[identity['parent_pid']]
        if parent['birth_clock_ticks'] > identity['birth_clock_ticks']:
            break
        chain.append(parent)
        identity = parent
    root = identity
    ancestors = {row['pid'] for row in chain}

    def owned():
        snapshot = linux_snapshot()
        current = snapshot.get(root['pid'])
        if not current or (current['birth_clock_ticks'], current['pid_namespace']) != (root['birth_clock_ticks'], root['pid_namespace']):
            return {}
        selected = {root['pid']: current}
        while True:
            added = {pid: row for pid, row in snapshot.items() if pid not in selected and row['parent_pid'] in selected and row['birth_clock_ticks'] >= selected[row['parent_pid']]['birth_clock_ticks']}
            if not added:
                return selected
            selected.update(added)

    commands = [('help', ['--help']), ('index_help', ['cli', 'index_repository', '--help']), ('trace_help', ['cli', 'trace_path', '--help']), ('index', ['cli', '--json', 'index_repository', '--repo-path', '/mnt/d/dianzi/backend/src', '--mode', 'full', '--name', PROJECT]), ('schema', ['cli', '--json', 'get_graph_schema', '--project', PROJECT]), ('architecture', ['cli', '--json', 'get_architecture', '--project', PROJECT, '--format', 'json'])]
    for label, function in [('create_application', 'api.app.create_application'), ('public_router', 'api.public_extension_routes.build_public_extension_router'), ('public_reads', 'api.public_extension_reads.PublicExtensionReadService'), ('investigation_execute', 'investigation.workflow_service.InvestigationWorkflowService.execute'), ('run_role', 'investigation.workflow_service._WorkflowRuntime.run_role'), ('revalidation_handlers', 'revalidation.runtime_policy.make_revalidation_job_handlers')]:
        commands.append((label, ['cli', '--json', 'trace_path', '--project', PROJECT, '--function-name', PROJECT + '.ai_intel.' + function, '--direction', 'both', '--depth', '3', '--max-output-tokens', '4000', '--include-evidence', 'true']))
    if RUN.name == 'supplement':
        commands = []
        for label, function in [('public_get_vuln', 'api.public_extension_reads.PublicExtensionReadService.get_vuln'), ('worker_execute', 'workers.executor.execute_job'), ('fan_in_guard', 'revalidation.fan_in.guard_completed_fan_in'), ('read_consumers', 'investigation.read_adapters.PostgresReadToolAdapter.read_tool'), ('source_report_node', 'investigation.source_report_node.read_enrichment_source_reports'), ('structured_reader', 'knowledge.structured_fact_proofs.StructuredFactProofReader.read')]:
            commands.append((label, ['cli', '--json', 'trace_path', '--project', PROJECT, '--function-name', PROJECT + '.ai_intel.' + function, '--direction', 'both', '--depth', '3', '--max-output-tokens', '4000', '--include-evidence', 'true']))
    if RUN.name == 'final_bc089809':
        commands = [('index', ['cli', '--json', 'index_repository', '--repo-path', '/mnt/d/dianzi/backend/src', '--mode', 'full', '--name', PROJECT])]
        for label, function in [('consume_job', 'workers.runtime.consume_job'), ('settings', 'infrastructure.settings.ApplicationSettings'), ('graph_apply_factory', 'knowledge.graph_projection.build_graph_apply_handler'), ('knowledge_change', 'retrieval.runtime_policy.make_knowledge_change_handler'), ('projection_factory', 'retrieval.runtime_policy.build_projection_job_handlers')]:
            commands.append((label, ['cli', '--json', 'trace_path', '--project', PROJECT, '--function-name', PROJECT + '.ai_intel.' + function, '--direction', 'both', '--depth', '3', '--max-output-tokens', '5000', '--include-evidence', 'true']))
    deadline = time.monotonic() + (45 if RUN.name == 'final_bc089809' else 170)
    peak = {}
    seen = {}
    outcomes = []
    for label, args in commands:
        started = now()
        monotonic_start = time.monotonic()
        failure = None
        command = [TOOL, *args]
        with (RUN / (label + '.stdout.log')).open('wb') as stdout, (RUN / (label + '.stderr.log')).open('wb') as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr, env={**os.environ, 'CBM_CACHE_DIR': CACHE})
            call_deadline = min(deadline, monotonic_start + 55)
            while process.poll() is None:
                current = owned()
                seen.update({(row['pid'], row['birth_clock_ticks'], row['pid_namespace']): row for row in current.values()})
                if len(current) > len(peak):
                    peak = current
                (RUN / 'linux_active.json').write_text(json.dumps({'peak_count': len(peak), 'active': list(current.values())}) + '\n')
                if len(current) > 10 or time.monotonic() >= call_deadline:
                    failure = 'owned_process_cap_or_timeout'
                    exact = linux_snapshot().get(process.pid)
                    if exact and (exact['pid'], exact['birth_clock_ticks'], exact['pid_namespace']) in seen:
                        process.kill()
                    break
                time.sleep(0.02)
            process.wait(timeout=5)
        receipt = {'command': command, 'started_at': started, 'ended_at': now(), 'elapsed_seconds': time.monotonic() - monotonic_start, 'exit_code': process.returncode, 'failure': failure, 'per_call_timeout_seconds': 55, 'cache': CACHE, 'source_tree_sha256': json.loads((RUN / 'source_before.json').read_text())['tree_sha256']}
        (RUN / (label + '.command.json')).write_text(json.dumps(receipt, indent=2) + '\n')
        outcomes.append(receipt)
        if failure or process.returncode:
            break
    cleanup = []
    for row in list(owned().values()):
        key = (row['pid'], row['birth_clock_ticks'], row['pid_namespace'])
        if key in seen and row['pid'] not in ancestors and row['name'].startswith('codebase-memory'):
            os.kill(row['pid'], signal.SIGTERM)
            cleanup.append(row)
    release = time.monotonic() + 3
    while time.monotonic() < release:
        remaining = [row for row in owned().values() if row['pid'] not in ancestors]
        if not remaining:
            break
        time.sleep(0.05)
    result = {'recorded_at': now(), 'control_chain': chain, 'peak_count': len(peak), 'peak_chain': list(peak.values()), 'remaining_owned_children': remaining, 'cleanup_exact_owned_identities': cleanup, 'outcomes': len(outcomes), 'expected_commands': len(commands), 'cli_elapsed_seconds': sum(row['elapsed_seconds'] for row in outcomes), 'total_budget_seconds': 180, 'global_pid1_docker_runc_excluded': True}
    (RUN / 'linux_resources.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('peak_count', 'outcomes', 'expected_commands', 'cli_elapsed_seconds')}))
    return bool(remaining or len(outcomes) != len(commands) or any(row['exit_code'] or row['failure'] for row in outcomes))


def windows_run():
    sys.path.insert(0, 'D:/wt/r14-qualified-root-integration/reports/runs/r14_qualified_root_integration_20261017')
    import process_metadata as metadata
    control, chain = metadata.control_root(metadata.current_identity())
    before = metadata.descendants(control)
    linux_run_path = '/mnt/d/dianzi/' + RUN.relative_to(ROOT).as_posix()
    command = ['wsl.exe', '-d', 'Ubuntu-22.04', '--exec', '/usr/bin/python3', '/mnt/d/dianzi/reports/runs/root_batch13_index_20261017/index_support.py', 'linux', linux_run_path]
    peak = {}
    seen = {}
    started = now()
    monotonic_start = time.monotonic()
    linux_peak = 0
    transient_live_json_reads = 0
    with (RUN / 'sequence.stdout.log').open('wb') as stdout, (RUN / 'sequence.stderr.log').open('wb') as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, cwd=ROOT)
        while process.poll() is None:
            current = metadata.descendants(control)
            seen.update(current)
            if len(current) > len(peak):
                peak = current
            live = RUN / 'linux_active.json'
            if live.exists():
                try:
                    linux_peak = json.loads(live.read_text())['peak_count']
                except json.JSONDecodeError:
                    transient_live_json_reads += 1
            (RUN / 'windows_active.json').write_text(json.dumps({'recorded_at': now(), 'peak_count': len(peak), 'peak_chain': list(peak.values()), 'active': list(current.values()), 'control_chain': chain}) + '\n')
            if len(peak) + linux_peak > 16 or time.monotonic() - monotonic_start > 180:
                (RUN / 'guard_failure.json').write_text(json.dumps({'recorded_at': now(), 'windows_tree': list(current.values()), 'linux_peak': linux_peak, 'reason': 'combined_owned_cap_or_total_deadline'}) + '\n')
                process.terminate()
                break
            time.sleep(0.02)
        process.wait(timeout=5)
    active = metadata.descendants(control)
    remaining = [row for pid, row in active.items() if pid not in before and pid in seen and metadata.identity(pid) == {'pid': pid, 'birth_utc': row['birth_utc']}]
    linux = json.loads((RUN / 'linux_resources.json').read_text())
    result = {'started_at': started, 'ended_at': now(), 'command': command, 'exit_code': process.returncode, 'elapsed_seconds': time.monotonic() - monotonic_start, 'windows_peak_count': len(peak), 'windows_peak_chain': list(peak.values()), 'control_chain': chain, 'remaining_owned_processes': remaining, 'linux_peak_count': linux['peak_count'], 'combined_peak_conservative': len(peak) + linux['peak_count'], 'cap': 16, 'known_linux_ancestor_wrappers_exit_with_wsl': True, 'transient_live_json_reads': transient_live_json_reads}
    (RUN / 'sequence.command.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return process.returncode or bool(remaining or result['combined_peak_conservative'] > 16)


if __name__ == '__main__':
    phase = sys.argv[1]
    if phase == 'freeze':
        print(json.dumps({key: value for key, value in freeze(sys.argv[2]).items() if key != 'files'}))
    elif phase == 'linux':
        raise SystemExit(linux_run())
    elif phase == 'windows':
        raise SystemExit(windows_run())
