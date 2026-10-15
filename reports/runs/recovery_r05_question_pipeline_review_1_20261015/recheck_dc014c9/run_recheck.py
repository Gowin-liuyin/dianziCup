import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
WT = Path('D:/wt/r05-pipe-recheck')
RUN = Path('D:/dianzi/reports/runs/recovery_r05_question_pipeline_review_1_20261015/recheck_dc014c9')
label = sys.argv[1]
assert not (RUN / (label + '.json')).exists()
environment = os.environ.copy()
environment['PYTHONPATH'] = os.pathsep.join([str(WT / 'backend/src'), str(WT), str(WT / 'backend/tests'), str(WT / 'backend/tests/integration')])
common = ['uv', 'run', '--frozen', '--extra', 'semantic']
commands = {
 'pg_regression': common + ['pytest', 'tests/integration/test_r05_question_api_pg.py', 'tests/integration/test_r05_vector_persistence.py', '--no-cov', '-q', '--junitxml=' + str(RUN / 'pg_regression.xml')],
 'routes_core': common + ['pytest', 'tests/unit/test_r05_question_routes.py', 'tests/unit/test_r05_grounded_answer.py', 'tests/contract/test_r05_grounded_answer_contract.py', 'tests/contract/test_r05_question_contracts.py', '--no-cov', '-q', '--junitxml=' + str(RUN / 'routes_core.xml')],
 'probes': common + ['pytest', '-p', 'conftest', str(RUN / 'test_review_recheck.py'), '--no-cov', '-q', '-s', '--junitxml=' + str(RUN / 'probes.xml')],
 'static': common + ['mypy', 'src'],
 'ruff': common + ['ruff', 'check', 'src', 'tests/integration/test_r05_question_api_pg.py', 'tests/unit/test_r05_question_routes.py'],
 'unit': common + ['pytest', 'tests/unit', '-q', '--junitxml=' + str(RUN / 'unit.xml')],
}
commands['probes_retry'] = [value.replace('probes.xml', 'probes_retry.xml') for value in commands['probes']]
commands['lease_frozen'] = common + ['pytest', '-p', 'conftest', str(RUN / 'frozen_tests_54bd6db/test_r05_question_api_pg.py'), '--no-cov', '-q', '--junitxml=' + str(RUN / 'lease_frozen.xml')]
cbm = ['wsl', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', '/usr/bin/env', 'CBM_CACHE_DIR=/tmp/dianzi-cbm-r05-question-pipeline-review-20261015', '/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp', 'cli', '--json']
commands['cbm_index'] = cbm + ['index_repository', '--repo-path', '/mnt/d/wt/r05-pipe-recheck/backend/src', '--name', 'r05-question-pipeline-review-dc014c9', '--mode', 'fast']
commands['cbm_schema'] = cbm + ['get_graph_schema', '--project', 'r05-question-pipeline-review-dc014c9']
commands['cbm_auth_trace'] = cbm + ['trace_path', '--project', 'r05-question-pipeline-review-dc014c9', '--function-name', 'lock_authenticated_scope', '--direction', 'both', '--include-tests', 'true']
commands['format'] = common + ['ruff', 'format', '--check', 'src/ai_intel/answering/service.py', 'src/ai_intel/api/auth_state.py', 'src/ai_intel/api/question_routes.py']
if label in {'pg_regression', 'probes', 'probes_retry', 'lease_frozen'}:
    private = subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', 'cat', '/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json'], capture_output=True, text=True, check=True, timeout=10)
    environment['TEST_DATABASE_URL'] = json.loads(private.stdout)['TEST_DATABASE_URL']
    environment['DIANZI_TEST_RUN_ID'] = 'r05_pgvector_20261015'
command = commands[label]
started = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
completed = subprocess.run(command, cwd=WT / 'backend', env=environment, capture_output=True, text=True, timeout=600)
output = completed.stdout + completed.stderr
if environment.get('TEST_DATABASE_URL'):
    output = output.replace(environment['TEST_DATABASE_URL'], '[redacted test connection]')
(RUN / (label + '.log')).write_text(output, encoding='utf-8')
record = {'started_at': started, 'completed_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'), 'cwd': str(WT / 'backend'), 'command': command, 'exit_code': completed.returncode, 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=WT, text=True).strip(), 'tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=WT, text=True).strip(), 'log': str(RUN / (label + '.log'))}
(RUN / (label + '.json')).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(record, ensure_ascii=False))
print(output[-5000:])
raise SystemExit(completed.returncode)



