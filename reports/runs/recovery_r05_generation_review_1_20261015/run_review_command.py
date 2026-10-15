import datetime
import json
import os
import pathlib
import subprocess
import sys
import time

base = pathlib.Path(__file__).resolve().parent
cwd = pathlib.Path('C:/Users/yinha/.codex/worktrees/recovery-r05-generation-review-1/dianzi/backend')
label, *command = sys.argv[1:]
receipt = base / (label + '.command.json')
if receipt.exists():
    raise SystemExit('label already exists')
env = os.environ.copy()
env['UV_PROJECT_ENVIRONMENT'] = 'C:/Users/yinha/.codex/review-r05-generation-1-runtime/.venv'
env['COVERAGE_FILE'] = 'C:/Users/yinha/.codex/review-r05-generation-1-runtime/.coverage.' + label
env['PYTHONPATH'] = str(cwd / 'src') + os.pathsep + str(cwd / 'tests/unit') + os.pathsep + str(cwd / 'tests/security')
for name in ('TEST_DATABASE_URL', 'TEST_REDIS_URL', 'TEST_SEARCH_URL', 'TEST_MINIO_ENDPOINT', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'DEEPSEEK_API_KEY'):
    env.pop(name, None)
env['APP_ENV'] = 'test'
env['DATA_MODE'] = 'fixture'
zone = datetime.timezone(datetime.timedelta(hours=8))
record = {'cwd': str(cwd), 'command': command, 'started_at': datetime.datetime.now(zone).isoformat(timespec='seconds'), 'coverage_file': env['COVERAGE_FILE'], 'data_mode': 'fixture', 'external_calls': 'none; local test sockets only'}
receipt.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
started = time.perf_counter()
with (base / (label + '.log')).open('w', encoding='utf-8') as log:
    result = subprocess.run(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
record.update(completed_at=datetime.datetime.now(zone).isoformat(timespec='seconds'), elapsed_seconds=time.perf_counter()-started, exit_code=result.returncode)
receipt.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(record, ensure_ascii=False))
print((base / (label + '.log')).read_text(encoding='utf-8')[-1600:])
raise SystemExit(result.returncode)
