import argparse
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

WT = Path('D:/wt/r05-pipe-review')
RUN = Path('D:/dianzi/reports/runs/recovery_r05_question_pipeline_review_1_20261015')
CBM = ['wsl', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', '/usr/bin/env', 'CBM_CACHE_DIR=/tmp/dianzi-cbm-r05-question-pipeline-review-20261015', '/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp', 'cli', '--json']
parser = argparse.ArgumentParser()
parser.add_argument('label')
args = parser.parse_args()
environment = os.environ.copy()
environment['PYTHONPATH'] = os.pathsep.join([str(WT / 'backend/src'), str(WT), str(WT / 'backend/tests'), str(WT / 'backend/tests/integration')])
label = args.label
common = ['uv', 'run', '--frozen', '--extra', 'semantic']
commands = {
  'core': common + ['pytest', 'tests/unit/test_r05_grounded_answer.py', 'tests/unit/test_r05_evidence_chunks.py', 'tests/unit/test_r05_generation.py', 'tests/contract/test_r05_grounded_answer_contract.py', 'tests/contract/test_r05_question_contracts.py', '--no-cov', '-q', '--junitxml=' + str(RUN / 'core.xml')],
  'unit': common + ['pytest', 'tests/unit', '-q', '--junitxml=' + str(RUN / 'unit.xml')],
  'probes': common + ['pytest', str(RUN / 'test_review_probes.py'), '--no-cov', '-q', '-s', '--junitxml=' + str(RUN / 'probes.xml')],
  'vector_pg': common + ['pytest', 'tests/integration/test_r05_vector_persistence.py', '--no-cov', '-q', '--junitxml=' + str(RUN / 'vector_pg.xml')],
  'static': common + ['mypy', 'src'],
  'ruff': common + ['ruff', 'check', 'src', 'tests/integration/test_r05_vector_persistence.py', 'tests/unit/test_r05_evidence_chunks.py'],
  'cbm_help': CBM + ['--help'],
  'cbm_index': CBM + ['index_repository', '--repo-path', '/mnt/d/wt/r05-pipe-review/backend/src', '--name', 'r05-question-pipeline-review', '--mode', 'fast'],
  'cbm_schema': CBM + ['get_graph_schema', '--project', 'r05-question-pipeline-review'],
  'cbm_trace': CBM + ['trace_path', '--project', 'r05-question-pipeline-review', '--function-name', 'ask', '--direction', 'both', '--include-tests', 'true'],
}
commands['probes_retry'] = commands['probes'][:6] + ['-p', 'conftest'] + commands['probes'][6:]
commands['probes_retry'] = [value.replace('probes.xml', 'probes_retry.xml') for value in commands['probes_retry']]
commands['probes_expired'] = [value.replace('probes_retry.xml', 'probes_expired.xml') for value in commands['probes_retry']]
commands['boundaries'] = [value.replace('test_review_probes.py', 'test_review_boundaries.py').replace('probes_retry.xml', 'boundaries.xml') for value in commands['probes_retry']]
commands['boundaries_retry'] = [value.replace('boundaries.xml', 'boundaries_retry.xml') for value in commands['boundaries']]
commands['cbm_route'] = CBM + ['trace_path', '--project', 'r05-question-pipeline-review', '--function-name', 'ask_question', '--direction', 'both', '--include-tests', 'true']
commands['cbm_read'] = CBM + ['trace_path', '--project', 'r05-question-pipeline-review', '--function-name', 'read_grounded_answer', '--direction', 'both', '--include-tests', 'true']
commands['cbm_help2'] = ['wsl', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', '/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp', '--help']
commands['format'] = common + ['ruff', 'format', '--check', 'src/ai_intel/answering/service.py', 'src/ai_intel/retrieval/service.py', 'src/ai_intel/api/question_routes.py', 'src/ai_intel/api/app.py', 'tests/integration/test_r05_vector_persistence.py', 'tests/unit/test_r05_evidence_chunks.py']
commands['auth_commit_race'] = [value.replace('test_review_probes.py', 'test_review_auth_commit_race.py').replace('probes_retry.xml', 'auth_commit_race.xml') for value in commands['probes_retry']]
commands['frozen_pg'] = common + ['pytest', '-p', 'conftest', str(RUN / 'frozen_tests_af73b3e/test_r05_question_api_pg.py'), '--no-cov', '-q', '--junitxml=' + str(RUN / 'frozen_pg.xml')]
commands['frozen_routes'] = common + ['pytest', '-p', 'conftest', str(RUN / 'frozen_tests_af73b3e/test_r05_question_routes.py'), '--no-cov', '-q', '--junitxml=' + str(RUN / 'frozen_routes.xml')]
command = commands[label]
if label in {'vector_pg', 'probes', 'probes_retry', 'probes_expired', 'boundaries', 'boundaries_retry', 'auth_commit_race', 'frozen_pg'}:
    private = subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', 'cat', '/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json'], capture_output=True, text=True, check=True, timeout=10)
    environment['TEST_DATABASE_URL'] = json.loads(private.stdout)['TEST_DATABASE_URL']
    environment['DIANZI_TEST_RUN_ID'] = 'r05_pgvector_20261015'
started = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
completed = subprocess.run(command, cwd=WT / 'backend', env=environment, capture_output=True, text=True, timeout=600)
output = completed.stdout + completed.stderr
for key in ['TEST_DATABASE_URL', 'TEST_REDIS_URL']:
    if environment.get(key):
        output = output.replace(environment[key], '[redacted test connection]')
(RUN / (label + '.log')).write_text(output, encoding='utf-8')
record = {'started_at': started, 'completed_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'), 'cwd': str(WT / 'backend'), 'command': command, 'exit_code': completed.returncode, 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=WT, text=True).strip(), 'tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=WT, text=True).strip(), 'log': str(RUN / (label + '.log'))}
(RUN / (label + '.json')).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(record, ensure_ascii=False))
print(output[-5000:])
raise SystemExit(completed.returncode)








