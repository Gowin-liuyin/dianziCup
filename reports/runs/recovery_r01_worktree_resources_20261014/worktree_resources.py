"""Reuse frozen resource probes for two separately bounded worktree test stacks."""

import argparse
import hashlib
import json
import pathlib
import socket
import subprocess
import sys
from dataclasses import dataclass


PRIOR_DIRECTORY = pathlib.Path(__file__).resolve().parent.parent / 'recovery_r01_resources_20261014'
assert hashlib.sha256((PRIOR_DIRECTORY / 'resources.py').read_bytes()).hexdigest() == (
    'f152515405e7a1462a9d01d24815c7a3f5ebe2548c380e589a67c436caf5baf0')
sys.path.insert(0, str(PRIOR_DIRECTORY))
sys.dont_write_bytecode = True
import resources


@dataclass(frozen=True)
class TestStack:
    run_id: str
    postgres_port: int
    redis_port: int


STACKS = {
    'quality': TestStack('r01_quality_20261014', 25434, 26381),
    'frontend': TestStack('r01_frontend_20261014', 25435, 26382),
}
IMAGES = {
    'postgres': 'pgvector/pgvector@sha256:00ba258a66dac104fd5171074a0084462a64a1369d8513f3d0a634e2f24d15bc',
    'redis': 'redis@sha256:4fa24486b8bcca8eec45ee0eb166edc674795e53a2b53d1a9ef263eecebaac85',
}


def select_stack(stack: TestStack) -> None:
    resources.PROJECT = 'dianzi-test-' + stack.run_id
    resources.TEST_CONFIG = resources.RUNTIME / ('test-services-' + stack.run_id)
    resources.POSTGRES_NAME = resources.PROJECT + '-postgres'
    resources.REDIS_NAME = resources.PROJECT + '-redis'
    resources.POSTGRES_VOLUME = resources.PROJECT + '-postgres-data'
    resources.REDIS_VOLUME = resources.PROJECT + '-redis-data'
    resources.POSTGRES_DATABASE = 'test_dianzi_' + stack.run_id
    resources.POSTGRES_USER = 'test_dianzi_' + stack.run_id.removesuffix('_20261014')
    resources.POSTGRES_PORT = stack.postgres_port
    resources.REDIS_PORT = stack.redis_port


def start_stack(stack: TestStack) -> None:
    select_stack(stack)
    lifecycle = json.loads((resources.RUNTIME / 'lifecycle.json').read_text())
    assert lifecycle['ended_at'] is None
    assert lifecycle['deadline'] == '2026-10-17T21:49:15+08:00'
    assert not resources.TEST_CONFIG.exists()
    for port in (stack.postgres_port, stack.redis_port):
        with socket.socket() as probe:
            assert probe.connect_ex(('127.0.0.1', port)) != 0
    for name in (resources.POSTGRES_NAME, resources.REDIS_NAME):
        assert resources.inspect_named('container', name) is None
    for volume in (resources.POSTGRES_VOLUME, resources.REDIS_VOLUME):
        assert resources.inspect_named('volume', volume) is None
    private_config = resources.create_private_config(999, 999)
    private_config['DIANZI_TEST_RUN_ID'] = stack.run_id
    (resources.TEST_CONFIG / 'connection.json').write_text(json.dumps(private_config))
    redis_config = resources.TEST_CONFIG / 'redis.conf'
    redis_config.write_text(redis_config.read_text().replace('maxmemory 192mb', 'maxmemory 64mb'))
    for volume in (resources.POSTGRES_VOLUME, resources.REDIS_VOLUME):
        resources.docker(['volume', 'create', '--label', 'dianzi.project=' + resources.PROJECT,
                          '--label', 'dianzi.mode=test', volume])
    common = ['--detach', '--network', 'host', '--cgroup-parent', '/dianzi-r01-20261014',
              '--label', 'dianzi.project=' + resources.PROJECT, '--label', 'dianzi.mode=test',
              '--security-opt', 'no-new-privileges', '--restart', 'no', '--log-driver', 'local',
              '--log-opt', 'max-size=10m', '--log-opt', 'max-file=2']
    resources.docker(['run', *common, '--name', resources.POSTGRES_NAME, '--memory', '512m',
                      '--memory-swap', '512m', '--cpus', '0.4', '--pids-limit', '128',
                      '--env', 'POSTGRES_DB=' + resources.POSTGRES_DATABASE,
                      '--env', 'POSTGRES_USER=' + resources.POSTGRES_USER,
                      '--env', 'POSTGRES_PASSWORD_FILE=/run/secrets/postgres-password',
                      '--env', 'POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256',
                      '--mount', 'type=bind,src=' + str(resources.TEST_CONFIG / 'postgres-password') +
                      ',dst=/run/secrets/postgres-password,readonly',
                      '--mount', 'type=volume,src=' + resources.POSTGRES_VOLUME + ',dst=/var/lib/postgresql/data',
                      '--health-cmd', 'pg_isready -h 127.0.0.1 -p ' + str(stack.postgres_port) +
                      ' -U ' + resources.POSTGRES_USER + ' -d ' + resources.POSTGRES_DATABASE,
                      '--health-interval', '5s', '--health-timeout', '3s', '--health-retries', '12',
                      IMAGES['postgres'], 'postgres', '-c', 'listen_addresses=127.0.0.1',
                      '-c', 'port=' + str(stack.postgres_port), '-c', 'max_connections=30',
                      '-c', 'shared_buffers=64MB'])
    resources.docker(['run', *common, '--name', resources.REDIS_NAME, '--memory', '128m',
                      '--memory-swap', '128m', '--cpus', '0.1', '--pids-limit', '64',
                      '--mount', 'type=bind,src=' + str(redis_config) + ',dst=/run/redis-test.conf,readonly',
                      '--mount', 'type=volume,src=' + resources.REDIS_VOLUME + ',dst=/data',
                      '--health-cmd', 'redis-cli -h 127.0.0.1 -p ' + str(stack.redis_port) +
                      ' ping 2>&1 | grep -q NOAUTH', '--health-interval', '5s',
                      '--health-timeout', '3s', '--health-retries', '12',
                      IMAGES['redis'], 'redis-server', '/run/redis-test.conf'])
    print(json.dumps({'at': resources.now(), 'run_id': stack.run_id,
                      'private_config': str(resources.TEST_CONFIG / 'connection.json'),
                      'database': resources.POSTGRES_DATABASE, 'user': resources.POSTGRES_USER,
                      'postgres_port': stack.postgres_port, 'redis_port': stack.redis_port}))


def kernel_limits(stack: TestStack) -> None:
    select_stack(stack)
    for name in (resources.POSTGRES_NAME, resources.REDIS_NAME):
        result = resources.docker(['inspect', '--format', '{{json .State}}', name])
        state = json.loads(result.stdout)
        assert state['Running'] and not state['OOMKilled']
        cgroup_line = pathlib.Path('/proc/' + str(state['Pid']) + '/cgroup').read_text().strip()
        assert cgroup_line.startswith('0::/dianzi-r01-20261014/')
        cgroup_path = pathlib.Path('/sys/fs/cgroup') / cgroup_line.split('::', 1)[1].lstrip('/')
        limits = {key: (cgroup_path / key).read_text().strip()
                  for key in ('memory.max', 'memory.swap.max', 'cpu.max', 'pids.max')}
        expected = ({'memory.max': '536870912', 'memory.swap.max': '0',
                     'cpu.max': '40000 100000', 'pids.max': '128'}
                    if name == resources.POSTGRES_NAME else
                    {'memory.max': '134217728', 'memory.swap.max': '0',
                     'cpu.max': '10000 100000', 'pids.max': '64'})
        assert limits == expected
        print(json.dumps({'at': resources.now(), 'name': name, 'kernel_cgroup': str(cgroup_path),
                          'kernel_limits': limits}))
    result = subprocess.run(['ss', '-ltnp', '( sport = :' + str(stack.postgres_port) +
                             ' or sport = :' + str(stack.redis_port) + ' )'],
                            capture_output=True, text=True, timeout=5, check=True)
    addresses = {line.split()[3] for line in result.stdout.splitlines()[1:]}
    assert addresses == {'127.0.0.1:' + str(stack.postgres_port), '127.0.0.1:' + str(stack.redis_port)}
    print(json.dumps({'at': resources.now(), 'listen_command': result.args,
                      'exit_code': result.returncode, 'listen_output': result.stdout,
                      'private_config_mode': oct((resources.TEST_CONFIG / 'connection.json').stat().st_mode & 0o777),
                      'parent_mode': oct(resources.TEST_CONFIG.stat().st_mode & 0o777)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('stack', choices=STACKS)
    parser.add_argument('action', choices=['start', 'kernel-limits'])
    arguments = parser.parse_args()
    stack = STACKS[arguments.stack]
    print(json.dumps({'started_at': resources.now(), 'run_id': stack.run_id,
                      'action': arguments.action}), flush=True)
    if arguments.action == 'start':
        start_stack(stack)
    else:
        kernel_limits(stack)
    print(json.dumps({'ended_at': resources.now(), 'run_id': stack.run_id, 'result': 'passed'}))


if __name__ == '__main__':
    main()
