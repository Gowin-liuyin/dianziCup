"""Prepare isolated real test services without touching project application code."""

import argparse
import json
import os
import pathlib
import secrets
import socket
import subprocess
import time
from datetime import datetime, timedelta, timezone


RUNTIME = pathlib.Path('/tmp/dianzi-docker-static-r01-20261014/runtime')
TEST_CONFIG = RUNTIME / 'test-services'
DOCKER = '/tmp/dianzi-docker-static-r01-20261014/portable/docker/docker'
PROJECT = 'dianzi-test-r01_20261014'
POSTGRES_NAME = PROJECT + '-postgres'
REDIS_NAME = PROJECT + '-redis'
POSTGRES_VOLUME = PROJECT + '-postgres-data'
REDIS_VOLUME = PROJECT + '-redis-data'
POSTGRES_PORT = 25432
REDIS_PORT = 26379
POSTGRES_DATABASE = 'test_dianzi_r01_20261014'
POSTGRES_USER = 'test_dianzi_r01'
ZONE = timezone(timedelta(hours=8))


def now():
    return datetime.now(ZONE).isoformat(timespec='seconds')


def docker(arguments, timeout=25, input_text=None, check=True):
    started_at = now()
    command = [DOCKER, '--config', str(RUNTIME / 'client-config'), '--host',
               'unix://' + str(RUNTIME / 'docker.sock'), *arguments]
    result = subprocess.run(command, text=True, input=input_text, capture_output=True,
                            timeout=timeout)
    record = {'started_at': started_at, 'ended_at': now(), 'command': command,
              'exit_code': result.returncode, 'stdout': result.stdout,
              'stderr': result.stderr}
    if TEST_CONFIG.exists():
        config_path = TEST_CONFIG / 'connection.json'
        if config_path.exists():
            private_config = json.loads(config_path.read_text())
            for key in ('postgres_password', 'redis_password'):
                secret = private_config[key]
                record['stdout'] = record['stdout'].replace(secret, '[redacted]')
                record['stderr'] = record['stderr'].replace(secret, '[redacted]')
    print(json.dumps(record, ensure_ascii=False), flush=True)
    if check and result.returncode:
        raise RuntimeError('Docker command failed with exit code ' + str(result.returncode))
    return result


def inspect_named(kind, name):
    result = docker([kind, 'inspect', name], check=False)
    return None if result.returncode else json.loads(result.stdout)[0]


def preflight():
    lifecycle = json.loads((RUNTIME / 'lifecycle.json').read_text())
    assert lifecycle['ended_at'] is None
    assert datetime.fromisoformat(lifecycle['deadline']) > datetime.now(ZONE)
    cgroup = pathlib.Path('/sys/fs/cgroup/dianzi-r01-20261014')
    limits = {name: (cgroup / name).read_text().strip()
              for name in ('memory.max', 'memory.swap.max', 'cpu.max', 'pids.max')}
    assert limits['memory.max'] == '8589934592'
    assert limits['cpu.max'] == '200000 100000'
    assert limits['pids.max'] == '2048'
    docker(['version', '--format', '{{json .Server}}'])
    docker(['ps', '-a', '--format', '{{.Names}}'])
    occupied_ports = []
    for port in (POSTGRES_PORT, REDIS_PORT):
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1', port)) == 0:
                occupied_ports.append(port)
    existing = {name: inspect_named('container', name) is not None
                for name in (POSTGRES_NAME, REDIS_NAME)}
    print(json.dumps({'at': now(), 'ports': [POSTGRES_PORT, REDIS_PORT],
                      'occupied_ports': occupied_ports, 'existing_containers': existing,
                      'project_limits': limits}, ensure_ascii=False))
    assert not occupied_ports and not any(existing.values())
    assert not TEST_CONFIG.exists()


def pull(image):
    docker(['pull', image], timeout=55)
    result = docker(['image', 'inspect', image, '--format', '{{json .RepoDigests}}'])
    digest = json.loads(result.stdout)[0]
    assert '@sha256:' in digest
    return digest


def create_private_config(postgres_uid, redis_uid):
    TEST_CONFIG.mkdir(mode=0o700)
    os.chmod(TEST_CONFIG, 0o700)
    private_config = {'project': PROJECT, 'postgres_host': '127.0.0.1',
                      'postgres_port': POSTGRES_PORT, 'postgres_database': POSTGRES_DATABASE,
                      'postgres_user': POSTGRES_USER, 'postgres_password': secrets.token_hex(32),
                      'redis_host': '127.0.0.1', 'redis_port': REDIS_PORT,
                      'redis_password': secrets.token_hex(32), 'created_at': now()}
    private_config['DIANZI_TEST_RUN_ID'] = 'r01_20261014'
    private_config['TEST_DATABASE_URL'] = (
        'postgresql+psycopg://' + POSTGRES_USER + ':' + private_config['postgres_password'] +
        '@127.0.0.1:' + str(POSTGRES_PORT) + '/' + POSTGRES_DATABASE)
    private_config['TEST_REDIS_URL'] = (
        'redis://:' + private_config['redis_password'] + '@127.0.0.1:' + str(REDIS_PORT) + '/0')
    private_config['NO_PROXY'] = '127.0.0.1,localhost'
    config_path = TEST_CONFIG / 'connection.json'
    config_path.write_text(json.dumps(private_config))
    os.chmod(config_path, 0o600)
    password_path = TEST_CONFIG / 'postgres-password'
    password_path.write_text(private_config['postgres_password'])
    os.chmod(password_path, 0o600)
    os.chown(password_path, postgres_uid, postgres_uid)
    redis_config_path = TEST_CONFIG / 'redis.conf'
    redis_config_path.write_text(
        'bind 127.0.0.1\nport ' + str(REDIS_PORT) + '\nprotected-mode yes\n' +
        'requirepass ' + private_config['redis_password'] + '\n' +
        'appendonly yes\nappendfsync everysec\ndir /data\nmaxmemory 192mb\n' +
        'maxmemory-policy noeviction\n')
    os.chmod(redis_config_path, 0o600)
    os.chown(redis_config_path, redis_uid, redis_uid)
    return private_config


def start():
    for name in (POSTGRES_NAME, REDIS_NAME):
        assert inspect_named('container', name) is None
    assert not TEST_CONFIG.exists()
    images = {}
    for role, tag in (('postgres', 'pgvector/pgvector:0.8.2-pg16'), ('redis', 'redis:7.4')):
        result = docker(['image', 'inspect', tag, '--format', '{{json .RepoDigests}}'])
        images[role] = json.loads(result.stdout)[0]
    image_uids = {}
    for role, account in (('postgres', 'postgres'), ('redis', 'redis')):
        result = docker(['run', '--rm', '--network', 'none', '--read-only',
                         '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                         '--memory', '64m', '--memory-swap', '64m', '--cpus', '0.1',
                         '--pids-limit', '16', '--cgroup-parent', '/dianzi-r01-20261014',
                         '--entrypoint', 'id', images[role], '-u', account])
        image_uids[role] = int(result.stdout.strip())
    private_config = create_private_config(image_uids['postgres'], image_uids['redis'])
    for volume in (POSTGRES_VOLUME, REDIS_VOLUME):
        assert inspect_named('volume', volume) is None
        docker(['volume', 'create', '--label', 'dianzi.project=' + PROJECT,
                '--label', 'dianzi.mode=test', volume])
    common = ['--detach', '--network', 'host', '--cgroup-parent', '/dianzi-r01-20261014',
              '--label', 'dianzi.project=' + PROJECT, '--label', 'dianzi.mode=test',
              '--security-opt', 'no-new-privileges', '--restart', 'no',
              '--log-driver', 'local', '--log-opt', 'max-size=10m', '--log-opt', 'max-file=2']
    docker(['run', *common, '--name', POSTGRES_NAME, '--memory', '1g',
            '--memory-swap', '1g', '--cpus', '0.75', '--pids-limit', '128',
            '--env', 'POSTGRES_DB=' + POSTGRES_DATABASE, '--env', 'POSTGRES_USER=' + POSTGRES_USER,
            '--env', 'POSTGRES_PASSWORD_FILE=/run/secrets/postgres-password',
            '--env', 'POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256',
            '--mount', 'type=bind,src=' + str(TEST_CONFIG / 'postgres-password') +
            ',dst=/run/secrets/postgres-password,readonly',
            '--mount', 'type=volume,src=' + POSTGRES_VOLUME + ',dst=/var/lib/postgresql/data',
            '--health-cmd', 'pg_isready -h 127.0.0.1 -p 25432 -U ' + POSTGRES_USER +
            ' -d ' + POSTGRES_DATABASE, '--health-interval', '5s', '--health-timeout', '3s',
            '--health-retries', '12', images['postgres'], 'postgres', '-c',
            'listen_addresses=127.0.0.1', '-c', 'port=25432', '-c', 'max_connections=50',
            '-c', 'shared_buffers=128MB'])
    docker(['run', *common, '--name', REDIS_NAME, '--memory', '256m',
            '--memory-swap', '256m', '--cpus', '0.25', '--pids-limit', '64',
            '--mount', 'type=bind,src=' + str(TEST_CONFIG / 'redis.conf') +
            ',dst=/run/redis-test.conf,readonly',
            '--mount', 'type=volume,src=' + REDIS_VOLUME + ',dst=/data',
            '--health-cmd', 'redis-cli -h 127.0.0.1 -p 26379 ping 2>&1 | grep -q NOAUTH',
            '--health-interval', '5s', '--health-timeout', '3s', '--health-retries', '12',
            images['redis'], 'redis-server', '/run/redis-test.conf'])
    (TEST_CONFIG / 'images.json').write_text(json.dumps(images))
    print(json.dumps({'at': now(), 'private_config_path': str(TEST_CONFIG / 'connection.json'),
                      'private_config_mode': oct((TEST_CONFIG / 'connection.json').stat().st_mode & 0o777),
                      'image_digests': images, 'database': private_config['postgres_database']}))


def postgres_sql(sql):
    return docker(['exec', '-i', POSTGRES_NAME, 'psql', '-U', POSTGRES_USER,
                   '-d', POSTGRES_DATABASE, '-p', str(POSTGRES_PORT),
                   '-v', 'ON_ERROR_STOP=1', '-A', '-t'], input_text=sql)


def redis_command(*parts):
    private_config = json.loads((TEST_CONFIG / 'connection.json').read_text())
    def send(connection, *items):
        payload = ('*' + str(len(items)) + '\r\n').encode()
        for item in items:
            encoded = item.encode()
            payload += ('$' + str(len(encoded)) + '\r\n').encode() + encoded + b'\r\n'
        connection.sendall(payload)
        return connection.recv(4096)
    with socket.create_connection(('127.0.0.1', REDIS_PORT), timeout=3) as connection:
        assert send(connection, 'AUTH', private_config['redis_password']) == b'+OK\r\n'
        result = send(connection, *parts)
    assert not result.startswith(b'-')
    print(json.dumps({'at': now(), 'redis_command': parts, 'result': result.decode()}))
    return result


def smoke():
    result = postgres_sql("SELECT current_database(), current_user, version();\n"
                          "SHOW listen_addresses;\nSHOW port;\n"
                          "CREATE EXTENSION IF NOT EXISTS vector;\n"
                          "SELECT extversion FROM pg_extension WHERE extname='vector';\n"
                          "CREATE TABLE IF NOT EXISTS r01_resource_probe (probe_id text PRIMARY KEY, "
                          "payload text NOT NULL, embedding vector(3));\n"
                          "INSERT INTO r01_resource_probe VALUES ('persistent-r01', 'real-pg-test', "
                          "'[1,2,3]') ON CONFLICT (probe_id) DO NOTHING;\n"
                          "SELECT probe_id,payload,embedding <-> '[1,2,3]' FROM r01_resource_probe;\n")
    assert 'persistent-r01|real-pg-test|0' in result.stdout
    assert '0.8.2' in result.stdout
    assert redis_command('PING') == b'+PONG\r\n'
    assert redis_command('SET', 'r01:resource:persistent', 'real-redis-test') == b'+OK\r\n'
    assert b'real-redis-test' in redis_command('GET', 'r01:resource:persistent')
    for name in (POSTGRES_NAME, REDIS_NAME):
        result = docker(['inspect', '--format', '{{json .State}}', name])
        state = json.loads(result.stdout)
        assert state['Running'] and not state['OOMKilled']


def persistence():
    docker(['restart', '--time', '10', POSTGRES_NAME, REDIS_NAME], timeout=30)
    for attempt in range(20):
        readiness = docker(['exec', POSTGRES_NAME, 'pg_isready', '-h', '127.0.0.1',
                            '-p', str(POSTGRES_PORT), '-U', POSTGRES_USER,
                            '-d', POSTGRES_DATABASE], check=False)
        if readiness.returncode == 0:
            break
        time.sleep(1)
    assert readiness.returncode == 0
    result = postgres_sql("SELECT probe_id,payload,embedding <-> '[1,2,3]' "
                          "FROM r01_resource_probe WHERE probe_id='persistent-r01';\n")
    assert result.stdout.strip() == 'persistent-r01|real-pg-test|0'
    assert b'real-redis-test' in redis_command('GET', 'r01:resource:persistent')
    print(json.dumps({'at': now(), 'postgres_restart_persistence': 'passed',
                      'redis_restart_persistence': 'passed'}))


def identity():
    for name in (POSTGRES_NAME, REDIS_NAME):
        record = inspect_named('container', name)
        assert record['Config']['Labels']['dianzi.project'] == PROJECT
        host = record['HostConfig']
        print(json.dumps({'name': name, 'state': record['State'], 'image': record['Config']['Image'],
                          'mounts': record['Mounts'], 'network': host['NetworkMode'],
                          'memory': host['Memory'], 'memory_swap': host['MemorySwap'],
                          'nano_cpus': host['NanoCpus'], 'pids_limit': host['PidsLimit'],
                          'cgroup_parent': host['CgroupParent']}))


def kernel_limits():
    for name in (POSTGRES_NAME, REDIS_NAME):
        record = inspect_named('container', name)
        assert record['Config']['Labels']['dianzi.project'] == PROJECT
        pid = record['State']['Pid']
        assert pid > 0
        cgroup_line = pathlib.Path('/proc/' + str(pid) + '/cgroup').read_text().strip()
        assert cgroup_line.startswith('0::/dianzi-r01-20261014/')
        cgroup_path = pathlib.Path('/sys/fs/cgroup') / cgroup_line.split('::', 1)[1].lstrip('/')
        limits = {key: (cgroup_path / key).read_text().strip()
                  for key in ('memory.max', 'memory.swap.max', 'cpu.max', 'pids.max')}
        expected = ({'memory.max': '1073741824', 'memory.swap.max': '0',
                     'cpu.max': '75000 100000', 'pids.max': '128'}
                    if name == POSTGRES_NAME else
                    {'memory.max': '268435456', 'memory.swap.max': '0',
                     'cpu.max': '25000 100000', 'pids.max': '64'})
        assert limits == expected
        print(json.dumps({'at': now(), 'container': name, 'pid': pid,
                          'kernel_cgroup': str(cgroup_path), 'kernel_limits': limits}))
    result = subprocess.run(['ss', '-ltnp', '( sport = :25432 or sport = :26379 )'],
                            text=True, capture_output=True, timeout=5, check=True)
    print(json.dumps({'at': now(), 'listen_command': result.args, 'exit_code': result.returncode,
                      'listen_output': result.stdout}))
    local_addresses = {line.split()[3] for line in result.stdout.splitlines()[1:]}
    assert local_addresses == {'127.0.0.1:25432', '127.0.0.1:26379'}
    modes = {path.name: oct(path.stat().st_mode & 0o777)
             for path in TEST_CONFIG.iterdir() if path.name in
             ('connection.json', 'postgres-password', 'redis.conf')}
    assert set(modes.values()) == {'0o600'}
    print(json.dumps({'at': now(), 'private_file_modes': modes,
                      'parent_mode': oct(TEST_CONFIG.stat().st_mode & 0o777)}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['preflight', 'pull-postgres', 'pull-redis',
                                         'start', 'smoke', 'persistence', 'identity', 'kernel-limits'])
    args = parser.parse_args()
    print(json.dumps({'action': args.action, 'started_at': now()}), flush=True)
    actions = {'preflight': preflight, 'pull-postgres': lambda: pull('pgvector/pgvector:0.8.2-pg16'),
               'pull-redis': lambda: pull('redis:7.4'), 'start': start, 'smoke': smoke,
               'persistence': persistence, 'identity': identity, 'kernel-limits': kernel_limits}
    actions[args.action]()
    print(json.dumps({'action': args.action, 'ended_at': now(), 'result': 'passed'}), flush=True)


if __name__ == '__main__':
    main()
